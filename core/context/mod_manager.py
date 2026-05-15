from __future__ import annotations

import importlib
import inspect
import os
import sys
from typing import List, Dict, Optional, TYPE_CHECKING

from psygnal import Signal

from config.settings import AppSettings, ModConfig
from config.manager import ConfigManager
from .mod import ContextMod

if TYPE_CHECKING:
    from .engine import ContextEngine

_mod_manager: Optional["ModManager"] = None


def get_mod_manager() -> Optional["ModManager"]:
    return _mod_manager


def set_mod_manager(manager: "ModManager") -> None:
    global _mod_manager
    _mod_manager = manager


class ModManager:
    mod_added = Signal(str)
    mod_removed = Signal(str)
    mod_toggled = Signal(str, bool)
    mods_changed = Signal()
    show_mod_ui_requested = Signal(str)

    def __init__(self, engine: ContextEngine, settings: AppSettings):
        self._engine = engine
        self._settings = settings

    def load_from_settings(self) -> None:
        for mod_config in self._settings.mod.mods:
            if mod_config.enabled:
                self._enable_mod(mod_config)

    def _enable_mod(self, mod_config: ModConfig) -> bool:
        mod = self._instantiate_mod(mod_config)
        if mod is None:
            print(f"[ModManager] _enable_mod: 实例化失败, name={mod_config.name}")
            return False
        try:
            self._engine.register_mod(mod)
            print(f"[ModManager] _enable_mod: 注册成功, name={mod_config.name}")
            return True
        except Exception:
            import traceback
            print(f"[ModManager] _enable_mod: 注册失败, name={mod_config.name}")
            traceback.print_exc()
            return False

    def _disable_mod(self, name: str) -> bool:
        return self._engine.unregister_mod(name)

    def _instantiate_mod(self, mod_config: ModConfig) -> Optional[ContextMod]:
        if not mod_config.class_path:
            print(f"[ModManager] _instantiate_mod: class_path 为空, name={mod_config.name}")
            return None
        try:
            module_path, class_name = mod_config.class_path.split(":")
            module = importlib.import_module(module_path)
            mod_class = getattr(module, class_name)

            mod_instance = mod_class()
            if mod_config.config:
                mod_instance.config = dict(mod_config.config)

            return mod_instance
        except Exception:
            import traceback
            print(f"[ModManager] _instantiate_mod 失败: name={mod_config.name}, class_path={mod_config.class_path}")
            traceback.print_exc()
            return None

    def enable_mod(self, name: str) -> bool:
        for mc in self._settings.mod.mods:
            if mc.name == name:
                if mc.enabled:
                    print(f"[ModManager] enable_mod: 已启用, 无需操作, name={name}")
                    return True
                if self._enable_mod(mc):
                    mc.enabled = True
                    self.mods_changed.emit()
                    self.mod_toggled.emit(name, True)
                    print(f"[ModManager] enable_mod: 成功, name={name}")
                    return True
                else:
                    print(f"[ModManager] enable_mod: _enable_mod 失败, name={name}")
        print(f"[ModManager] enable_mod: 未找到配置, name={name}")
        return False

    def disable_mod(self, name: str) -> bool:
        for mc in self._settings.mod.mods:
            if mc.name == name:
                if not mc.enabled:
                    return True
                if self._disable_mod(name):
                    mc.enabled = False
                    self.mods_changed.emit()
                    self.mod_toggled.emit(name, False)
                    return True
        return False

    def add_mod(self, config: ModConfig) -> bool:
        for existing in self._settings.mod.mods:
            if existing.name == config.name:
                return False
        self._settings.mod.mods.append(config)
        if config.enabled:
            self._enable_mod(config)
        self.mod_added.emit(config.name)
        self.mods_changed.emit()
        return True

    def remove_mod(self, name: str) -> bool:
        for i, mc in enumerate(self._settings.mod.mods):
            if mc.name == name:
                if mc.enabled:
                    self._disable_mod(name)
                del self._settings.mod.mods[i]
                self.mod_removed.emit(name)
                self.mods_changed.emit()
                return True
        return False

    def get_mod_instance(self, name: str):
        return self._engine.mod_registry.get_mod(name)

    def get_mod_configs(self) -> List[ModConfig]:
        return list(self._settings.mod.mods)

    def save(self) -> None:
        ConfigManager.save_settings(self._settings)

    @staticmethod
    def discover_available_mods() -> List[dict]:
        import importlib.util

        mods_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "mods"
        )
        if not os.path.isdir(mods_dir):
            return []

        available: List[dict] = []

        for fname in sorted(os.listdir(mods_dir)):
            if fname.startswith("_") or not fname.endswith(".py"):
                continue
            module_name = f"mods.{fname[:-3]}"
            file_path = os.path.join(mods_dir, fname)
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            except Exception:
                continue

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if not issubclass(obj, ContextMod) or obj is ContextMod:
                    continue
                if getattr(obj, "__abstractmethods__", None):
                    continue
                try:
                    name = getattr(obj, "name", fname[:-3])
                except Exception:
                    name = fname[:-3]
                available.append({
                    "name": name,
                    "class_path": f"{module_name}:{obj.__name__}",
                    "description": getattr(obj, "description", ""),
                    "version": getattr(obj, "version", "1.0"),
                    "author": getattr(obj, "author", ""),
                    "has_config_widget": hasattr(module, "mod_config_widget"),
                    "has_main_widget": hasattr(module, "mod_main_widget"),
                    "main_widget_title": getattr(module, "mod_main_title", lambda: name)(),
                })

        return available
