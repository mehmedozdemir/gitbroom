from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from gitbroom.config.settings import load_settings
from gitbroom.core.logging_setup import setup_logging
from gitbroom.ui.theme.theme import ThemeManager


def _icon_path() -> Path:
    # PyInstaller unpacks data files to sys._MEIPASS at runtime
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent.parent.parent))
    return base / "assets" / "icons" / "icon.png"


def run_app() -> int:
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("GitBroom")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("GitBroom")

    icon_path = _icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    settings = load_settings()
    theme = ThemeManager()
    theme.apply(app, settings.theme)

    from gitbroom.ui.main_window import MainWindow
    window = MainWindow(settings, theme)
    window.show()

    return app.exec()
