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

from PyQt6.QtWidgets import QFrame,QTextBrowser


# ----------------------------
# Markdown 渲染核心（线程安全，不碰 Qt）
# ----------------------------

@dataclass(frozen=True)
class MarkdownRenderOptions:
    code_style: str = "vs"
    markdown_extensions: Tuple[str, ...] = (
        "extra",        # tables 等常用扩展集合
        "sane_lists",   # 修复/增强列表解析一致性（嵌套列表更稳）
        "md_in_html",
        "nl2br",        # 你原来需要的“单换行 -> <br>”
    )


class MarkdownRenderer:
    # 允许前面有最多 3 个空格（Markdown 标准允许）
    _FENCE_RE = re.compile(
        r"(?m)^(?P<indent>[ \t]*)```(?P<lang>[^\n`]*)\n"
        r"(?P<code>[\s\S]*?)"
        r"(?:^(?P=indent)```[ \t]*$|\Z)"
    )

    @staticmethod
    def _normalize_fence_starts(text: str) -> str:
        """
        关键修复：
        如果 ``` 出现在一行中间（比如标题后面、冒号后面），
        强制在它前面插入换行，避免 fenced code 被标题吞掉。
        """
        # 把形如： "...非空白...```" 改为 "...非空白...\n```"
        return re.sub(r"(?m)^([^\n]*\S)(```)", r"\1\n\2", text)
    
    @staticmethod
    def render(raw_text: str, *, options: MarkdownRenderOptions) -> str:
        # 关键：如果你的文本整体被意外缩进（比如每行前面都有 4 个空格），
        # 会导致列表被当成“缩进代码块”。dedent 可以把这种“整体缩进”纠正回来。
        raw_text = textwrap.dedent(raw_text)

        # 1) 提取 fenced code block -> token，避免 markdown 扩展互相打架
        nonce = uuid.uuid4().hex
        code_blocks: List[Tuple[str, str]] = []

        def take_block(m: re.Match) -> str:
            indent = m.group("indent") or ""
            lang = (m.group("lang") or "").strip()
            code = m.group("code") or ""
            code_blocks.append((lang, code))
            token = f"@@CODEBLOCK_{nonce}_{len(code_blocks) - 1}@@"
            # token 强制独立成行（保留原 indent，避免破坏列表嵌套）
            return f"{indent}{token}"

        temp = MarkdownRenderer._FENCE_RE.sub(take_block, raw_text)

        # 2) 不要再做“数字序号转 span”的替换 —— 那会直接破坏 4. 这种有序列表语法
        # （删除你原来的 fake-ol 正则）

        # 3) Markdown -> HTML
        html_content = markdown.markdown(
            temp,
            extensions=list(options.markdown_extensions),
            output_format="html5"
        )

        # 4) 把 token 换回高亮后的代码块
        formatter = HtmlFormatter(
            style=options.code_style,
            noclasses=True,
            nobackground=True,
            linenos=False,
            nowrap=True,  # 只输出 <span style=...>，不输出自带 <pre style=...>
        )

        for i, (lang, code) in enumerate(code_blocks):
            token = f"@@CODEBLOCK_{nonce}_{i}@@"
            html_content = html_content.replace(token, MarkdownRenderer._render_code(lang, code, formatter))

        # 5) $$...$$ 公式（按你原逻辑保留）
        html_content = re.sub(
            r"\$\$(.*?)\$\$",
            lambda m: f'<span class="math-formula">{html.escape(m.group(1))}</span>',
            html_content,
            flags=re.DOTALL
        )

        return html_content

    @staticmethod
    def _render_code(lang: str, code: str, formatter: HtmlFormatter) -> str:
        code = code.rstrip("\n")
        lang_l = (lang or "").lower()

        if lang_l in ("math", "latex", "tex"):
            return f'<div class="math-formula">{html.escape(code)}</div>'

        try:
            lexer = get_lexer_by_name(lang_l, stripall=False) if lang_l else TextLexer(stripall=False)
            inner = highlight(code, lexer, formatter)  # 仅 span 片段
            # 自己包 pre/code：字号会跟随 QTextBrowser 全局字体
            return f'<pre class="code-block"><code>{inner}</code></pre>'
        except Exception:
            return f'<pre class="code-block"><code>{html.escape(code)}</code></pre>'


# ----------------------------
# 异步任务（QThreadPool）
# ----------------------------

class _RenderSignals(QObject):
    finished = pyqtSignal(str, int)  # html, request_id


class _MarkdownRenderTask(QRunnable):
    def __init__(self, raw_text: str, request_id: int, options: MarkdownRenderOptions):
        super().__init__()
        self.raw_text = raw_text
        self.request_id = request_id
        self.options = options
        self.signals = _RenderSignals()

    def run(self) -> None:
        html_result = MarkdownRenderer.render(self.raw_text, options=self.options)
        self.signals.finished.emit(html_result, self.request_id)


# ----------------------------
# QTextBrowser 控件
# ----------------------------

class ChatapiTextBrowser(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._options = MarkdownRenderOptions(code_style="vs")

        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)  # 只保留最新渲染，避免流式时 CPU 飙升

        self._current_request_id = 0
        self._pending_text = ""
        self._pending_request_id = 0

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._dispatch_render)

        self.setup_ui()

    def setup_ui(self):
        # 关键：显式把 ul/ol 的样式打开，避免被你其他 CSS 重置掉导致“看起来没渲染”
        self.setStyleSheet("""
            /* 列表显示修复 */
            ul, ol {
                margin: 0.4em 0;
                padding-left: 1.4em;
                list-style-position: outside;
            }
            ul { list-style-type: disc; }
            ol { list-style-type: decimal; }
            li { margin: 0.2em 0; }

            pre {
                margin: 0.4em 0;
                padding: 0.6em 0.8em;
                border-radius: 8px;
                background: rgba(0,0,0,0.06);
                white-space: pre-wrap;
            }
            code {
                font-family: Consolas, Menlo, Monaco, "Courier New", monospace;
            }
            .math-formula {
                font-family: Consolas, Menlo, Monaco, "Courier New", monospace;
                background: rgba(0,0,0,0.06);
                padding: 0.2em 0.4em;
                border-radius: 6px;
            }
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
        task = _MarkdownRenderTask(self._pending_text, self._pending_request_id, self._options)
        task.signals.finished.connect(self.handle_processed_html, Qt.ConnectionType.QueuedConnection)
        self._pool.start(task)

    def handle_processed_html(self, html_content: str, request_id: int) -> None:
        if request_id != self._current_request_id:
            return
        super().setHtml(html_content)
        self._after_set_html()

    def _after_set_html(self) -> None:
        pass

    def setSource(self, url):
        # 禁用自动导航（保留你的行为）
        pass


class MarkdownTextBrowser(ChatapiTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

        self.anchorClicked.connect(lambda url: QDesktopServices.openUrl(QUrl(url.toString())))

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._is_streaming = False
        # 快速取用内容,markdown toPlainText会少字
        self.content=''

        self._geo_timer = QTimer(self)
        self._geo_timer.setSingleShot(True)
        self._geo_timer.timeout.connect(self.updateGeometry)
        self.document().contentsChanged.connect(self._schedule_geometry_update)

    def setMarkdown(self, text: str, is_streaming: bool = False):
        self._is_streaming = is_streaming
        self.content=text#用于快速取用
        super().setMarkdown(text, debounce_ms=60 if is_streaming else 0)

    def _after_set_html(self) -> None:
        self._schedule_geometry_update()

    def _schedule_geometry_update(self):
        self._geo_timer.start(80 if self._is_streaming else 0)

    def sizeHint(self) -> QSize:
        margins = self.contentsMargins()
        w = max(0, self.width() - margins.left() - margins.right())
        if w > 0:
            self.document().setTextWidth(w)

        doc_h = self.document().documentLayout().documentSize().height()
        total_h = doc_h + margins.top() + margins.bottom()
        return QSize(self.width(), int(total_h))

