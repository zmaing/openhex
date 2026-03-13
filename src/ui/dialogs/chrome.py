"""
Shared helpers for dialog headers and validation chrome.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QFrame, QVBoxLayout, QWidget


def create_dialog_header(title: str, subtitle: str = "") -> QWidget:
    """Create a shared dialog hero header."""
    card = QFrame()
    card.setObjectName("dialogHeaderCard")

    layout = QVBoxLayout()
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(6)

    title_label = QLabel(str(title or "").strip())
    title_label.setObjectName("dialogHeroTitle")
    layout.addWidget(title_label)

    if subtitle:
        subtitle_label = QLabel(str(subtitle).strip())
        subtitle_label.setObjectName("dialogHeroSubtitle")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)

    card.setLayout(layout)
    return card


def set_invalid_state(widget, invalid: bool) -> None:
    """Toggle a shared invalid visual state on any editable widget."""
    widget.setProperty("invalid", bool(invalid))
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()
