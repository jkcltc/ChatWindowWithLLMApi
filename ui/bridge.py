from PyQt6.QtCore import QObject, pyqtSignal
from psygnal import Signal, SignalInstance
from typing import Optional, Union, Iterable
from functools import partial
import inspect
from core.session.signals import ChatFlowManagerSignalBus

def _create_qt_bus_class(psygnal_cls, class_name="QtSignalBus"):
    qt_signals = {}

    for name in dir(psygnal_cls):
        if name.startswith('_'):
            continue

        attr = getattr(psygnal_cls, name)
        if isinstance(attr, Signal):
            types = []
            if hasattr(attr, 'signature') and isinstance(attr.signature, inspect.Signature):
                for param in attr.signature.parameters.values():
                    if param.annotation != inspect.Parameter.empty:
                        types.append(param.annotation)
                    else:
                        types.append(object)
            else:
                types = getattr(attr, 'types', ())

            types = tuple(types) if isinstance(types, (list, tuple)) else ()

            qt_signals[name] = pyqtSignal(*types)

    def bus_connect(self,
                    source,
                    exclude: Optional[Union[str, Iterable[str]]] = None,
                    include: Optional[Union[str, Iterable[str]]] = None):
        def to_set(val):
            if val is None: return set()
            if isinstance(val, str): return {val}
            return set(val)

        exclude_set = to_set(exclude)
        include_set = to_set(include)

        for name in dir(source):
            if name.startswith('_'):
                continue
            if name in exclude_set:
                continue
            if include_set and name not in include_set:
                continue

            source_attr = getattr(source, name)
            if isinstance(source_attr, SignalInstance) and hasattr(self, name):
                target_attr = getattr(self, name)


                source_attr.connect(target_attr.emit)

    new_class = type(class_name, (QObject,), qt_signals)
    setattr(new_class, 'bus_connect', bus_connect)
    return new_class

# 实例化使用
UiSignalBridge = _create_qt_bus_class(ChatFlowManagerSignalBus, "UiSignalBridge")
