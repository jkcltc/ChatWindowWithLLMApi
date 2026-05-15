from PyQt6.QtCore import QObject, Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QWidget

from core.context.mod_manager import ModManager
from ui.bridge import create_qt_bridge_class

ModManagerUiBridge = create_qt_bridge_class(ModManager, "ModManagerUiBridge")


class ModMainWindowManager(QObject):
    def __init__(self, mod_manager: ModManager, parent: QObject = None):
        super().__init__(parent)
        self._mod_manager = mod_manager
        self._windows: dict[str, QDialog] = {}

        self._bridge = ModManagerUiBridge()
        self._bridge.bus_connect(
            mod_manager,
            include=["show_mod_ui_requested", "mod_toggled", "mod_removed"]
        )
        self._bridge.show_mod_ui_requested.connect(self._on_show_ui_requested)
        self._bridge.mod_toggled.connect(self._on_mod_toggled)
        self._bridge.mod_removed.connect(self._on_mod_removed)

    def _on_show_ui_requested(self, name: str):
        self.open_mod_window(name)

    def _on_mod_toggled(self, name: str, enabled: bool):
        if not enabled:
            self.close_mod_window(name)

    def _on_mod_removed(self, name: str):
        self.close_mod_window(name)

    def open_mod_window(self, name: str, widget: QWidget = None, title: str = ""):
        if name in self._windows:
            self._windows[name].raise_()
            self._windows[name].activateWindow()
            return

        if widget is None:
            import sys
            mod = self._mod_manager.get_mod_instance(name)
            if mod is None:
                return
            module_name = mod.__class__.__module__
            module = sys.modules.get(module_name)
            if module is None or not hasattr(module, "mod_main_widget"):
                return
            widget = module.mod_main_widget(mod)
            title = getattr(module, "mod_main_title", lambda: name)()

        if widget is None:
            return

        dlg = QDialog()
        dlg.setWindowTitle(title or name)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = QVBoxLayout(dlg)
        layout.addWidget(widget)
        dlg.finished.connect(lambda: self._windows.pop(name, None))
        self._windows[name] = dlg
        dlg.show()

    def close_mod_window(self, name: str):
        if name in self._windows:
            self._windows[name].close()

    def disconnect_all(self):
        self._bridge.disconnect_all()
