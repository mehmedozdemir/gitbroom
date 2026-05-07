from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QApplication

_THEME_DIR = Path(__file__).parent


class ThemeManager:
    def __init__(self) -> None:
        self._current: str = "dark"

    def apply_dark(self, app: QApplication) -> None:
        self._apply(app, "dark")

    def apply_light(self, app: QApplication) -> None:
        self._apply(app, "light")

    def apply(self, app: QApplication, theme: str) -> None:
        self._apply(app, theme)

    def current(self) -> str:
        return self._current

    def toggle(self, app: QApplication) -> str:
        next_theme = "light" if self._current == "dark" else "dark"
        self._apply(app, next_theme)
        return next_theme

    def _apply(self, app: QApplication, theme: str) -> None:
        qss_file = _THEME_DIR / f"style_{theme}.qss"
        if not qss_file.exists():
            return
        app.setStyleSheet(qss_file.read_text(encoding="utf-8"))
        self._current = theme
