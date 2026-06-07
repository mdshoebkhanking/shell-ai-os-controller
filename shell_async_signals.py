from __future__ import annotations

import threading
import time
from typing import Any, Callable


class Signal:
    """Small Qt-like signal used by Electron/Python runtimes without PyQt."""

    def __init__(self) -> None:
        self._callbacks: list[Callable[..., Any]] = []
        self._lock = threading.RLock()

    def connect(self, callback: Callable[..., Any]) -> None:
        if not callable(callback):
            return
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def disconnect(self, callback: Callable[..., Any] | None = None) -> None:
        with self._lock:
            if callback is None:
                self._callbacks.clear()
                return
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass

    def emit(self, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            callbacks = list(self._callbacks)
        for callback in callbacks:
            try:
                callback(*args, **kwargs)
            except Exception:
                pass


class SignalDescriptor:
    def __init__(self) -> None:
        self._name = ""

    def __set_name__(self, _owner: type[Any], name: str) -> None:
        self._name = f"__signal_{name}"

    def __get__(self, instance: Any, _owner: type[Any] | None = None) -> Signal:
        if instance is None:
            return self  # type: ignore[return-value]
        signal = instance.__dict__.get(self._name)
        if signal is None:
            signal = Signal()
            instance.__dict__[self._name] = signal
        return signal


def signal(*_args: Any, **_kwargs: Any) -> SignalDescriptor:
    return SignalDescriptor()


class WorkerThread(threading.Thread):
    """Threading backend with the subset of QThread API Shell uses."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        super().__init__(daemon=True)

    def isRunning(self) -> bool:
        return self.is_alive()

    def wait(self, timeout: int | float | None = None) -> bool:
        seconds: float | None
        if timeout is None:
            seconds = None
        else:
            seconds = float(timeout) / 1000.0
        self.join(seconds)
        return not self.is_alive()

    def quit(self) -> None:
        stop = getattr(self, "stop_listening", None) or getattr(self, "shutdown", None)
        if callable(stop):
            stop()

    @staticmethod
    def msleep(milliseconds: int | float) -> None:
        time.sleep(max(0.0, float(milliseconds) / 1000.0))
