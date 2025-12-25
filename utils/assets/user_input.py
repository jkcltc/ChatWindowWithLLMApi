from __future__ import annotations

import sys
import base64
from pathlib import Path

from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QPropertyAnimation,
    QByteArray,
    QBuffer,
    QIODevice,
    QSize,
    QUrl,
    QFileInfo,
    QTimer,
)
from PyQt6.QtGui import (
    QImage,
    QPixmap,
    QPainter,
    QDesktopServices,
    QTextCursor,  # 新增
)
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QTextEdit,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QStackedLayout,
    QGraphicsOpacityEffect,
    QFileIconProvider,
    QSizePolicy,
    QDialog,
    QScrollArea,
    QFrame,
)

# --------------------- 常量与工具函数 ---------------------

IMAGE_EXTS = {"png", "jpg", "jpeg", "bmp", "gif", "webp"}
AUDIO_EXTS = {"wav", "mp3", "aiff", "aac", "ogg", "flac"}
VIDEO_EXTS = {"mp4", "mpeg", "mov", "webm"}
ATTACHABLE_EXTS = IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS


def path_ext(path: str) -> str:
    return Path(path).suffix.lower().lstrip(".")


def guess_qimage_format(ext: str) -> str:
    ext = (ext or "").lower()
    if ext in {"jpg", "jpeg"}:
        return "JPEG"
    if ext == "bmp":
        return "BMP"
    if ext == "gif":
        return "GIF"
    if ext == "webp":
        return "WEBP"
    return "PNG"


def qimage_to_base64(image: QImage, fmt: str = "PNG") -> tuple[str, str]:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, fmt.upper())
    buf.close()

    raw = bytes(ba.data())
    b64 = base64.b64encode(raw).decode("ascii")

    fmt_lower = fmt.lower()
    mime = "image/jpeg" if fmt_lower == "jpeg" else f"image/{fmt_lower}"
    return b64, mime


def _mime_for_audio_ext(ext: str) -> str:
    ext = (ext or "").lower()
    mapping = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "aiff": "audio/aiff",
        "aac": "audio/aac",
        "ogg": "audio/ogg",
        "flac": "audio/flac",
    }
    return mapping.get(ext, f"audio/{ext}" if ext else "audio/wav")


def _mime_for_video_ext(ext: str) -> str:
    ext = (ext or "").lower()
    mapping = {
        "mp4": "video/mp4",
        "mpeg": "video/mpeg",
        "mov": "video/quicktime",
        "webm": "video/webm",
    }
    return mapping.get(ext, f"video/{ext}" if ext else "video/mp4")


def _file_to_b64(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    return base64.b64encode(data).decode("ascii")


# --------------------- 附件数据结构 ---------------------


class AttachmentKind:
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class Attachment:
    def __init__(
        self,
        kind: str,
        path: str | None = None,
        image: QImage | None = None,
        ext: str | None = None,
    ):
        self.kind = kind
        self.path = path
        self.image = image
        self.ext = (ext.lower() if ext else (path_ext(path) if path else ""))

    def to_pixmap(self, size: QSize | None = None) -> QPixmap:
        pix = QPixmap()

        if self.kind == AttachmentKind.IMAGE:
            if self.image is not None:
                pix = QPixmap.fromImage(self.image)
            elif self.path:
                pix = QPixmap(self.path)
        else:
            if self.path:
                provider = QFileIconProvider()
                icon = provider.icon(QFileInfo(self.path))
                if not icon.isNull():
                    if size is None:
                        size = QSize(96, 96)
                    pix = icon.pixmap(size)

        if size is not None and not pix.isNull() and self.kind == AttachmentKind.IMAGE:
            pix = pix.scaled(
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return pix


# --------------------- 附件预览控件 ---------------------


class AttachmentPreview(QWidget):
    previewRequested = pyqtSignal(object)
    removeRequested = pyqtSignal(object)

    def __init__(self, attachment: Attachment, parent: QWidget | None = None):
        super().__init__(parent)
        self.attachment = attachment
        self._init_ui()

    def _init_ui(self):
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = self.attachment.to_pixmap(QSize(96, 96))
        if not pix.isNull():
            self.label.setPixmap(pix)
        else:
            self.label.setText("无预览")
            self.label.setStyleSheet("color: gray; font-size: 10px;")

        self.overlay = QWidget()
        self.overlay.setStyleSheet("background: rgba(0, 0, 0, 60); border-radius: 4px;")

        overlay_layout = QHBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(4, 4, 4, 4)
        overlay_layout.setSpacing(4)

        self.preview_btn = QPushButton("预览")
        self.remove_btn = QPushButton("移除")
        for btn in (self.preview_btn, self.remove_btn):
            btn.setFlat(True)
            btn.setStyleSheet(
                """
                QPushButton {
                    color: white;
                    background: rgba(0,0,0,0);
                    border: 1px solid rgba(255,255,255,180);
                    border-radius: 3px;
                    padding: 2px 4px;
                    font-size: 10px;
                }
                QPushButton:hover { background: rgba(255,255,255,40); }
                """
            )

        overlay_layout.addWidget(self.preview_btn)
        overlay_layout.addStretch(1)
        overlay_layout.addWidget(self.remove_btn)

        self.stack = QStackedLayout(self)
        self.stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self.stack.addWidget(self.label)
        self.stack.addWidget(self.overlay)
        self.stack.setCurrentWidget(self.overlay)

        self.effect = QGraphicsOpacityEffect(self.overlay)
        self.overlay.setGraphicsEffect(self.effect)
        self.effect.setOpacity(0.0)

        self.fade_in = QPropertyAnimation(self.effect, b"opacity", self)
        self.fade_in.setDuration(150)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)

        self.fade_out = QPropertyAnimation(self.effect, b"opacity", self)
        self.fade_out.setDuration(150)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)

        self.preview_btn.clicked.connect(lambda: self.previewRequested.emit(self.attachment))
        self.remove_btn.clicked.connect(lambda: self.removeRequested.emit(self.attachment))

        self.setToolTip(self.attachment.path or "")

    def enterEvent(self, event):
        self.fade_out.stop()
        self.fade_in.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.fade_in.stop()
        self.fade_out.start()
        super().leaveEvent(event)


# --------------------- 右侧附件容器控件（竖向+滚动） ---------------------


class AttachmentContainer(QWidget):
    attachmentAdded = pyqtSignal(object)
    attachmentRemoved = pyqtSignal(object)
    previewRequested = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.attachments: list[Attachment] = []

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setFixedWidth(150)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.inner = QWidget()
        self.inner_layout = QVBoxLayout(self.inner)
        self.inner_layout.setContentsMargins(0, 0, 0, 0)
        self.inner_layout.setSpacing(6)
        self.inner_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.inner)
        outer.addWidget(self.scroll)

        self.setVisible(False)

    def add_image(self, image: QImage, ext: str = "png", source_path: str | None = None) -> Attachment:
        att = Attachment(kind=AttachmentKind.IMAGE, path=source_path, image=image, ext=ext)
        self._add_attachment(att)
        return att

    def add_file(self, path: str) -> Attachment | None:
        ext = path_ext(path)
        if ext not in ATTACHABLE_EXTS:
            return None

        if ext in IMAGE_EXTS:
            img = QImage(path)
            if img.isNull():
                return None
            return self.add_image(img, ext=ext, source_path=path)

        kind = AttachmentKind.AUDIO if ext in AUDIO_EXTS else AttachmentKind.VIDEO
        att = Attachment(kind=kind, path=path, image=None, ext=ext)
        self._add_attachment(att)
        return att

    def clear(self):
        for i in reversed(range(self.inner_layout.count())):
            item = self.inner_layout.takeAt(i)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self.attachments.clear()
        self.setVisible(False)

    def image_attachments(self) -> list[Attachment]:
        return [a for a in self.attachments if a.kind == AttachmentKind.IMAGE]

    def first_image_attachment(self) -> Attachment | None:
        imgs = self.image_attachments()
        return imgs[0] if imgs else None

    def _add_attachment(self, att: Attachment):
        self.attachments.append(att)

        preview = AttachmentPreview(att, self.inner)
        self.inner_layout.addWidget(preview)

        preview.previewRequested.connect(self.previewRequested)
        preview.removeRequested.connect(self._on_preview_remove_requested)

        self.setVisible(True)
        self.attachmentAdded.emit(att)

    def _on_preview_remove_requested(self, att: Attachment):
        for i in range(self.inner_layout.count()):
            item = self.inner_layout.itemAt(i)
            w = item.widget()
            if isinstance(w, AttachmentPreview) and w.attachment is att:
                self.inner_layout.takeAt(i)
                w.deleteLater()
                break

        if att in self.attachments:
            self.attachments.remove(att)

        self.setVisible(bool(self.attachments))
        self.attachmentRemoved.emit(att)


# --------------------- 自定义 QTextEdit：拦截粘贴 & 拖拽 ---------------------


class InterceptingTextEdit(QTextEdit):
    def __init__(self, multi_modal: "MultiModalTextEdit"):
        super().__init__(multi_modal)
        self.multi_modal = multi_modal
        self.setAcceptDrops(True)

    def insertFromMimeData(self, source):
        if source.hasUrls():
            handled_any = False
            for url in source.urls():
                if not url.isLocalFile():
                    continue
                if self.multi_modal.handle_dropped_path(url.toLocalFile()):
                    handled_any = True
            if handled_any:
                return

        if source.hasImage():
            img = source.imageData()
            if isinstance(img, QPixmap):
                img = img.toImage()
            elif not isinstance(img, QImage):
                img = QImage(img)
            self.multi_modal.handle_pasted_image(img)
            return

        super().insertFromMimeData(source)

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            for url in md.urls():
                if url.isLocalFile() and self.multi_modal.is_path_acceptable(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        if md.hasImage():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            handled_any = False
            for url in md.urls():
                if not url.isLocalFile():
                    continue
                if self.multi_modal.handle_dropped_path(url.toLocalFile()):
                    handled_any = True
            if handled_any:
                event.acceptProposedAction()
                return

        if md.hasImage():
            img = md.imageData()
            if isinstance(img, QPixmap):
                img = img.toImage()
            elif not isinstance(img, QImage):
                img = QImage(img)
            self.multi_modal.handle_pasted_image(img)
            event.acceptProposedAction()
            return

        super().dropEvent(event)


# --------------------- 图片预览对话框 ---------------------


class ImagePreviewDialog(QDialog):
    def __init__(self, attachment: Attachment, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("图片预览")
        layout = QVBoxLayout(self)

        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = attachment.to_pixmap()
        if not pix.isNull():
            pix = pix.scaled(
                QSize(900, 700),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(pix)
        else:
            label.setText("无法加载图片")

        layout.addWidget(label)
        self.resize(920, 740)


# --------------------- 主控件：MultiModalTextEdit ---------------------


class MultiModalTextEdit(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._background_pixmap: QPixmap | None = None
        self._placeholder_text: str = ""

        # 创建布局
        self.root_layout = QHBoxLayout(self)
        self.root_layout.setContentsMargins(4, 4, 4, 4)
        self.root_layout.setSpacing(6)

        # 创建 TextEdit
        self.text_edit: InterceptingTextEdit | None = None
        self._create_text_edit()

        # 创建附件容器
        self.attachment_container = AttachmentContainer(self)
        self.root_layout.addWidget(self.attachment_container, 0)

        self.attachment_container.attachmentAdded.connect(self._on_attachment_added)
        self.attachment_container.attachmentRemoved.connect(self._on_attachment_removed)
        self.attachment_container.previewRequested.connect(self._on_preview_requested)

    def _create_text_edit(self):
        """创建新的 TextEdit 并插入到布局最前面"""
        self.text_edit = InterceptingTextEdit(self)
        self.text_edit.setPlaceholderText(self._placeholder_text)
        self.root_layout.insertWidget(0, self.text_edit, 1)

    def _recreate_text_edit(self):
        """
        销毁并重建 QTextEdit，恢复文本和光标状态。
        这是解决光标显示异常的核心方法。
        你就说管不管用吧。
        """
        if self.text_edit is None:
            return

        # 1. 保存当前状态
        saved_text = self.text_edit.toPlainText()
        saved_cursor = self.text_edit.textCursor()
        saved_position = saved_cursor.position()
        saved_anchor = saved_cursor.anchor()
        saved_placeholder = self.text_edit.placeholderText()
        had_focus = self.text_edit.hasFocus()

        # 2. 移除并销毁旧的 TextEdit
        self.root_layout.removeWidget(self.text_edit)
        self.text_edit.deleteLater()
        self.text_edit = None

        # 3. 创建新的 TextEdit
        self._placeholder_text = saved_placeholder
        self._create_text_edit()

        # 4. 恢复文本
        self.text_edit.setPlainText(saved_text)

        # 5. 恢复光标位置和选择
        new_cursor = self.text_edit.textCursor()
        # 先移动到 anchor 位置
        new_cursor.setPosition(saved_anchor, QTextCursor.MoveMode.MoveAnchor)
        # 再移动到 position 位置（保持选择）
        new_cursor.setPosition(saved_position, QTextCursor.MoveMode.KeepAnchor)
        self.text_edit.setTextCursor(new_cursor)

        # 6. 恢复焦点
        if had_focus:
            self.text_edit.setFocus()

    # ---- 拖拽/粘贴处理 ----

    def is_path_acceptable(self, path: str) -> bool:
        return path_ext(path) in ATTACHABLE_EXTS

    def handle_dropped_path(self, path: str) -> bool:
        ext = path_ext(path)
        if ext not in ATTACHABLE_EXTS:
            return False

        if ext in IMAGE_EXTS:
            img = QImage(path)
            if img.isNull():
                return False
            self.attachment_container.add_image(img, ext=ext, source_path=path)
            return True

        self.attachment_container.add_file(path)
        return True

    def handle_pasted_image(self, image: QImage):
        self.attachment_container.add_image(image, ext="png")

    # ---- 背景逻辑 ----

    def _update_background_from_first_image(self):
        first = self.attachment_container.first_image_attachment()
        if first is None:
            self._background_pixmap = None
        else:
            pix = first.to_pixmap()
            self._background_pixmap = pix if not pix.isNull() else None
        self.update()

    def _on_attachment_added(self, att: Attachment):
        if att.kind == AttachmentKind.IMAGE:
            if self.attachment_container.first_image_attachment() is att:
                self._update_background_from_first_image()

        # 延迟重建 TextEdit
        QTimer.singleShot(0, self._recreate_text_edit)

    def _on_attachment_removed(self, att: Attachment):
        if att.kind == AttachmentKind.IMAGE:
            self._update_background_from_first_image()

        # 延迟重建 TextEdit
        QTimer.singleShot(0, self._recreate_text_edit)

    def _on_preview_requested(self, att: Attachment):
        if att.kind == AttachmentKind.IMAGE:
            ImagePreviewDialog(att, self).exec()
        elif att.path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(att.path))

    # ---- 对外 API ----

    def toPlainText(self) -> str:
        return self.text_edit.toPlainText() if self.text_edit else ""

    def setText(self, text: str):
        if self.text_edit:
            self.text_edit.setPlainText(text)

    def setPlaceholderText(self, text: str):
        self._placeholder_text = text
        if self.text_edit:
            self.text_edit.setPlaceholderText(text)

    def clear(self):
        if self.text_edit:
            self.text_edit.clear()
        self.attachment_container.clear()
        self._background_pixmap = None
        self.update()

    # ---- multimodal 导出 ----

    def get_multimodal_content(self) -> list[dict]:
        parts: list[dict] = []

        for att in self.attachment_container.attachments:
            if att.kind == AttachmentKind.IMAGE:
                if att.image is not None:
                    img = att.image
                elif att.path:
                    img = QImage(att.path)
                else:
                    continue
                if img.isNull():
                    continue

                fmt = guess_qimage_format(att.ext or "png")
                b64, mime = qimage_to_base64(img, fmt=fmt)
                parts.append(
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
                )

            elif att.kind == AttachmentKind.AUDIO:
                if not att.path:
                    continue
                b64 = _file_to_b64(att.path)
                if not b64:
                    continue
                mime = _mime_for_audio_ext(att.ext or "wav")
                parts.append(
                    {"type": "audio_url", "audio_url": {"url": f"data:{mime};base64,{b64}"}}
                )

            elif att.kind == AttachmentKind.VIDEO:
                if not att.path:
                    continue
                b64 = _file_to_b64(att.path)
                if not b64:
                    continue
                mime = _mime_for_video_ext(att.ext or "mp4")
                parts.append(
                    {"type": "video_url", "video_url": {"url": f"data:{mime};base64,{b64}"}}
                )

        text = self.toPlainText().strip()
        if text:
            parts.append({"type": "text", "text": text})

        return parts

    # ---- 背景绘制 ----

    def paintEvent(self, event):
        if self._background_pixmap is not None and not self._background_pixmap.isNull():
            painter = QPainter(self)
            painter.setOpacity(0.5)
            scaled = self._background_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(0, 0, scaled)
            painter.end()

        super().paintEvent(event)


# --------------------- Demo ---------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)

    host = QWidget()
    host.setWindowTitle("MultiModalTextEdit - Attachments Right")
    layout = QVBoxLayout(host)

    mm = MultiModalTextEdit()
    mm.setPlaceholderText("输入文字；粘贴/拖拽图片或音频/视频文件到文本框区域…")
    layout.addWidget(mm)

    host.resize(900, 600)
    host.show()

    sys.exit(app.exec())