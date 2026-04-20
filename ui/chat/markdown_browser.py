import re
import textwrap
import uuid
from dataclasses import dataclass
from typing import List, Tuple

import markdown
import html
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.lexers.special import TextLexer

from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QObject, QRunnable, QThreadPool, QUrl, QSize
)
from PyQt6.QtGui import QTextOption, QDesktopServices
from PyQt6.QtWidgets import QFrame, QTextBrowser


# ----------------------------
# Markdown 渲染核心（线程安全，不碰 Qt）
# ----------------------------

@dataclass(frozen=True)
class MarkdownRenderOptions:
    code_style: str = "vs"
    markdown_extensions: Tuple[str, ...] = (
        "extra",
        "sane_lists",
        "md_in_html",
        "nl2br",
    )


class MarkdownRenderer:
    _FENCE_RE = re.compile(
        r"(?m)^(?P<indent>[ \t]*)```(?P<lang>[^\n`]*)\n"
        r"(?P<code>[\s\S]*?)"
        r"(?:^(?P=indent)```[ \t]*$|\Z)"
    )

    @staticmethod
    def _normalize_fence_starts(text: str) -> str:
        return re.sub(r"(?m)^([^\n]*\S)(```)", r"\1\n\2", text)

    @staticmethod
    def render(raw_text: str, *, options: MarkdownRenderOptions) -> str:
        raw_text = textwrap.dedent(raw_text)

        nonce = uuid.uuid4().hex
        code_blocks: List[Tuple[str, str]] = []

        def take_block(m: re.Match) -> str:
            indent = m.group("indent") or ""
            lang = (m.group("lang") or "").strip()
            code = m.group("code") or ""
            code_blocks.append((lang, code))
            token = f"@@CODEBLOCK_{nonce}_{len(code_blocks) - 1}@@"
            return f"{indent}{token}"

        temp = MarkdownRenderer._FENCE_RE.sub(take_block, raw_text)

        html_content = markdown.markdown(
            temp,
            extensions=list(options.markdown_extensions),
            output_format="html5"
        )

        formatter = HtmlFormatter(
            style=options.code_style,
            noclasses=True,
            nobackground=True,
            linenos=False,
            nowrap=True,
        )

        for i, (lang, code) in enumerate(code_blocks):
            token = f"@@CODEBLOCK_{nonce}_{i}@@"
            html_content = html_content.replace(
                token, MarkdownRenderer._render_code(lang, code, formatter))

        html_content = re.sub(
            r"\$\$(.*?)\$\$",
            lambda m: f'<span class="math-formula">'
                      f'{html.escape(m.group(1))}</span>',
            html_content,
            flags=re.DOTALL
        )

        return html_content

    @staticmethod
    def _render_code(lang: str, code: str, formatter: HtmlFormatter) -> str:
        code = code.rstrip("\n")
        lang_l = (lang or "").lower()

        if lang_l in ("math", "latex", "tex"):
            return (f'<div class="math-formula">'
                    f'{html.escape(code)}</div>')

        try:
            lexer = (get_lexer_by_name(lang_l, stripall=False)
                     if lang_l else TextLexer(stripall=False))
            inner = highlight(code, lexer, formatter)
            return f'<pre class="code-block"><code>{inner}</code></pre>'
        except Exception:
            return (f'<pre class="code-block">'
                    f'<code>{html.escape(code)}</code></pre>')


# ----------------------------
# 异步任务（QThreadPool）
# ----------------------------

class _RenderSignals(QObject):
    finished = pyqtSignal(str, int)


class _MarkdownRenderTask(QRunnable):
    def __init__(self, raw_text: str, request_id: int,
                 options: MarkdownRenderOptions):
        super().__init__()
        self.raw_text = raw_text
        self.request_id = request_id
        self.options = options
        self.signals = _RenderSignals()

    def run(self) -> None:
        html_result = MarkdownRenderer.render(
            self.raw_text, options=self.options)
        self.signals.finished.emit(html_result, self.request_id)


# ----------------------------
# QTextBrowser 控件
# ----------------------------

class ChatapiTextBrowser(QTextBrowser):
    renderStarted = pyqtSignal()
    renderFinished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._options = MarkdownRenderOptions(code_style="vs")
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._current_request_id = 0
        self._pending_text = ""
        self._pending_request_id = 0
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._dispatch_render)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            ul, ol { margin: 0.4em 0; padding-left: 1.4em;
                     list-style-position: outside; }
            ul { list-style-type: disc; }
            ol { list-style-type: decimal; }
            li { margin: 0.2em 0; }
            pre { margin: 0.4em 0; padding: 0.6em 0.8em; border-radius: 8px;
                  background: rgba(0,0,0,0.06); white-space: pre-wrap; }
            code { font-family: Consolas, Menlo, Monaco,
                   "Courier New", monospace; }
            .math-formula {
                font-family: Consolas, Menlo, Monaco,
                             "Courier New", monospace;
                background: rgba(0,0,0,0.06);
                padding: 0.2em 0.4em; border-radius: 6px; }
        """)
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)

    def setMarkdown(self, text: str, debounce_ms: int = 0) -> None:
        self._current_request_id += 1
        rid = self._current_request_id
        self._pending_text = text
        self._pending_request_id = rid
        if debounce_ms > 0:
            self._debounce_timer.start(debounce_ms)
        else:
            self._debounce_timer.stop()
            self._dispatch_render()

    def _dispatch_render(self) -> None:
        self.renderStarted.emit()
        task = _MarkdownRenderTask(
            self._pending_text, self._pending_request_id, self._options)
        task.signals.finished.connect(
            self.handle_processed_html, Qt.ConnectionType.QueuedConnection)
        self._pool.start(task)

    def handle_processed_html(self, html_content: str,
                              request_id: int) -> None:
        if request_id != self._current_request_id:
            self.renderFinished.emit()
            return

        # 允许子类在 setHtml 前后介入
        self._before_set_html()
        super().setHtml(html_content)
        self._after_set_html()
        self.renderFinished.emit()

    def _before_set_html(self) -> None:
        pass

    def _after_set_html(self) -> None:
        pass

    def invalidate_pending_renders(self):
        self._debounce_timer.stop()
        self._current_request_id += 1

    def setSource(self, url):
        pass


class MarkdownTextBrowser(ChatapiTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFrameShape(QFrame.Shape.NoFrame)
        # 使用 WrapAtWordBoundaryOrAnywhere 防止长单词撑破布局
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

        self.anchorClicked.connect(lambda url: QDesktopServices.openUrl(QUrl(url.toString())))

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._is_streaming = False
        # 用于快速取用内容
        self.content = ''
        # 用于标记是否正在进行程序内部的全量更新
        self._is_programmatic_update = False

        self._geo_timer = QTimer(self)
        self._geo_timer.setSingleShot(True)
        self._geo_timer.timeout.connect(self.updateGeometry)

        # 监听内容变化，用于处理流式更新或窗口Resize时的重绘
        self.document().contentsChanged.connect(self._schedule_geometry_update)

    def setMarkdown(self, text: str, is_streaming: bool = False):
        self._is_streaming = is_streaming
        self.content = text
        super().setMarkdown(text, debounce_ms=60 if is_streaming else 0)

    def _before_set_html(self) -> None:
        """在设置HTML前冻结界面，防止中间态渲染"""
        # 如果不是流式传输（即全量更新），我们冻结界面
        if not self._is_streaming:
            self._is_programmatic_update = True
            self.setUpdatesEnabled(False)

    def _after_set_html(self) -> None:
        """在设置HTML后强制计算布局，然后解冻"""
        if self._is_streaming:
            # 流式传输保持原有逻辑，依赖 contentsChanged 触发定时器
            self._schedule_geometry_update()
        else:
            # 全量更新：
            # 1. 立即强制更新文档宽度，确保高度计算正确 (跳过150ms等待)
            self._force_layout_calculation()

            # 2. 通知父控件尺寸已变更 (Layout系统会调用 sizeHint)
            self.updateGeometry()

            # 3. 标记程序更新结束
            self._is_programmatic_update = False

            # 4. 关键：使用 singleShot(0) 将恢复重绘的操作放入事件队列末尾。
            # 这确保了 Qt 的 Layout 系统已经完成了对 updateGeometry 的响应和父级布局调整，
            # 然后我们再开启绘制，从而避免看到布局跳变的过程。
            QTimer.singleShot(0, self._enable_updates)

    def _enable_updates(self):
        """恢复重绘"""
        self.setUpdatesEnabled(True)
        # 强制重绘一次以确保显示最新状态
        self.repaint()

    def _force_layout_calculation(self):
        """手动强制触发布局计算"""
        margins = self.contentsMargins()
        w = max(0, self.width() - margins.left() - margins.right())
        if w > 0:
            # 设置宽度会触发布局计算，为接下来的 sizeHint 提供正确基础
            self.document().setTextWidth(w)

    def _schedule_geometry_update(self):
        """计划更新几何形状（处理 Resize 或 流式更新）"""
        # 如果是我们正在进行的setHtml全量更新，忽略这个信号，
        # 因为我们在 _after_set_html 里已经手动处理了，不需要定时器
        if self._is_programmatic_update:
            return

        self._geo_timer.start(150)

    def resizeEvent(self, e):
        """窗口大小改变时，需要重新计算高度"""
        super().resizeEvent(e)
        self._force_layout_calculation()
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        """计算控件所需大小"""
        # 确保文档宽度与控件宽度一致（减去边距）
        margins = self.contentsMargins()
        w = max(0, self.width() - margins.left() - margins.right())

        # 注意：在 sizeHint 中调用 setTextWidth 是为了确保 documentSize().height() 是基于当前宽度的。
        # 配合 updateGeometry 使用时，这能保证高度随宽度动态调整。
        if w > 0:
            self.document().setTextWidth(w)

        doc_h = self.document().documentLayout().documentSize().height()
        total_h = doc_h + margins.top() + margins.bottom()

        # 向上取整避免最后一行被切掉
        return QSize(self.width(), int(total_h) + 1)