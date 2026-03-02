from PyQt6.QtCore import QObject, pyqtSignal,pyqtBoundSignal
from psygnal import Signal, SignalInstance
from typing import Optional, Union, Iterable
import inspect
from core.signals import MainBus
class QtBaseSignalBridge(QObject):
    """
    Qt 信号桥接基类
    只负责提供跨总线连线/断线的通用方法，不包含具体信号。
    """
    def bus_connect(self, source, exclude=None, include=None):
        def to_set(val):
            if val is None: 
                return set()
            if isinstance(val, str): 
                return {val}
            return set(val)

        exclude_set = to_set(exclude)
        include_set = to_set(include)
        include_active = include is not None

        for name in dir(source):
            if name.startswith('_'): 
                continue
            if name in exclude_set: 
                continue
            if include_active and name not in include_set:
                continue

            try:
                source_attr = getattr(source, name)
            except Exception as e:
                print(f"Failed to get attribute {name}: {e}")
                continue

            if hasattr(self, name):
                target_attr = getattr(self, name)
                
                if (callable(getattr(source_attr, 'connect', None)) and 
                    callable(getattr(target_attr, 'emit', None))):
                    source_attr.connect(target_attr.emit)


    def disconnect_all(self):
        for name in dir(self):
            if name.startswith('_'): continue
            attr = getattr(self, name)
            if callable(getattr(attr, 'disconnect', None)):
                if not isinstance(attr, pyqtBoundSignal) and not isinstance(attr,SignalInstance):
                    return
                try:
                    attr.disconnect()
                except (TypeError, ValueError) as e:
                    pass

def create_qt_bridge_class(psygnal_cls, class_name="QtSignalBridge"):
    """
    读取 psygnal 类的定义，动态生成带有对应 pyqtSignal 的 Qt 类
    """
    qt_signals = {}

    for name in dir(psygnal_cls):
        if name.startswith('_'): continue

        attr = getattr(psygnal_cls, name)
        if isinstance(attr, Signal):
            types = []
            for param in attr.signature.parameters.values():
                if param.annotation in (int, float, str, bool, list, dict, tuple):
                    types.append(param.annotation)
                else:
                    types.append(object)
            types = tuple(types) if types else ()

            qt_signals[name] = pyqtSignal(*types)

    return type(class_name, (QtBaseSignalBridge,), qt_signals)

UiMainSignalBridge = create_qt_bridge_class(MainBus, "UiMainSignalBridge")

    