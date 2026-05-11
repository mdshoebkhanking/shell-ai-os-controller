"""glass_backdrop — DISABLED safe-stub version.

The original GlassBackdrop polled `parent.grab(rect)` + QGraphicsBlurEffect
every 80 ms to fake macOS-style backdrop blur. On Windows + RDP that loop
saturated the Qt main thread, queueing input events for 5–15 s and
occasionally swallowing presses entirely (because each refresh hide()'d
and show()'d the host widget, tearing through child event delivery).

Symptoms reported by the user:
    - "ek page se dosre main jane bohot hi time lagra"
    - "1 nai horra 2 nai hotta 3 pata nai 4 5 se 15 se zada hi lagri"
    - "4 5 bar click karne per horra nai to voh bhi nai horra"

This module now ships a **no-op** GlassBackdrop so existing imports keep
working but no per-frame work happens. The translucent `vibrancy_layer_qss`
gradient already gives a passable Apple-glass look without the cost.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget


class GlassBackdrop(QWidget):
    """No-op backdrop. Keeps the original constructor signature so callers
    don't break, but never runs a timer, never grabs the parent, never
    hides/shows the host. Effectively an invisible passive widget."""

    def __init__(
        self,
        host: QWidget,
        *,
        blur_radius: int = 28,
        refresh_ms: int = 80,
    ) -> None:
        super().__init__(host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setGeometry(host.rect())
        self.hide()  # nothing to draw

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass

    def set_blur_radius(self, r: int) -> None:
        pass


__all__ = ["GlassBackdrop"]
