"""Project-wide Python compatibility shims.

Python automatically imports ``sitecustomize`` when it is present on
``sys.path``. Shell still supports older system Python builds where a few
typing symbols live in ``typing_extensions`` instead of ``typing``; some
newer runtime packages import them from ``typing`` unconditionally.
"""

from __future__ import annotations


def _patch_typing() -> None:
    try:
        import typing
        import typing_extensions
    except Exception:
        return

    for name in (
        "TypeAlias",
        "TypeGuard",
        "Self",
        "Required",
        "NotRequired",
        "Never",
        "LiteralString",
        "dataclass_transform",
        "assert_never",
        "override",
    ):
        if not hasattr(typing, name) and hasattr(typing_extensions, name):
            try:
                setattr(typing, name, getattr(typing_extensions, name))
            except Exception:
                pass


_patch_typing()
