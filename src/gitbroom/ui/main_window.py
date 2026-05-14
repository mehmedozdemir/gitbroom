from __future__ import annotations

import logging
import subprocess

from PyQt6.QtCore import QByteArray, QSettings, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStatusBar,
    QTabBar,
    QTabWidget,
    QToolBar,
    QPushButton,
    QWidget,
)

from gitbroom.core.models import AppSettings
from gitbroom.ui.theme.icons import icon
from gitbroom.ui.theme.theme import ThemeManager
from gitbroom.ui.widgets.repo_tab import RepoTab

logger = logging.getLogger(__name__)

_QSETTINGS_ORG = "GitBroom"
_QSETTINGS_APP = "GitBroom"
_NEW_TAB_LABEL = "Yeni Sekme"


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._settings = settings
        self._theme = theme_manager
        self._git_user_name, self._git_user_email = self._fetch_git_user_info()
        self._setup_window()
        self._build_ui()
        self._setup_shortcuts()
        self._restore_state()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle("GitBroom — Git Branch Temizleyici")
        self.resize(1200, 750)
        self.setMinimumSize(900, 600)

    def _build_ui(self) -> None:
        self._build_toolbar()
        self._build_status_bar()
        self._build_tab_widget()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Ana Araç Çubuğu")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        title = QLabel("  GitBroom")
        title.setObjectName("sectionHeader")
        toolbar.addWidget(title)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        if self._git_user_name or self._git_user_email:
            user_text = self._git_user_name or ""
            if self._git_user_email:
                user_text += f"  ‹{self._git_user_email}›"
            user_label = QLabel(f"👤  {user_text.strip()}")
            user_label.setStyleSheet("color: #a6adc8; font-size: 12px; padding-right: 8px;")
            toolbar.addWidget(user_label)

        self._btn_settings = QPushButton("Ayarlar")
        self._btn_settings.setIcon(icon("settings"))
        self._btn_settings.setShortcut("Ctrl+,")
        self._btn_settings.clicked.connect(self._on_open_settings)
        toolbar.addWidget(self._btn_settings)

        self._btn_about = QPushButton()
        self._btn_about.setIcon(icon("info"))
        self._btn_about.setFixedWidth(32)
        self._btn_about.setToolTip("Hakkında")
        self._btn_about.clicked.connect(self._on_about)
        toolbar.addWidget(self._btn_about)

        self._btn_theme = QPushButton("🌙")
        self._btn_theme.setFixedWidth(36)
        self._btn_theme.setToolTip("Tema değiştir")
        self._btn_theme.clicked.connect(self._on_toggle_theme)
        toolbar.addWidget(self._btn_theme)

    def _build_tab_widget(self) -> None:
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabCloseRequested.connect(self._on_close_tab)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs.tabBar().setStyleSheet("QTabBar::tab { min-width: 180px; }")

        # "+" button on the tab bar
        self._btn_new_tab = QPushButton()
        self._btn_new_tab.setIcon(icon("add"))
        self._btn_new_tab.setFixedSize(28, 24)
        self._btn_new_tab.setToolTip("Yeni sekme  (Ctrl+T)")
        self._btn_new_tab.setFlat(True)
        self._btn_new_tab.clicked.connect(self._add_tab)
        self._tabs.setCornerWidget(self._btn_new_tab, Qt.Corner.TopRightCorner)

        self.setCentralWidget(self._tabs)

        # Open one default tab
        self._add_tab()

    def _build_status_bar(self) -> None:
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Hazır — Bir repo seçin ve 'Tara' butonuna tıklayın.")

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self._add_tab)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self._close_current_tab)

    # ── Tab management ────────────────────────────────────────────────────────

    def _add_tab(self, repo_path: str | None = None) -> RepoTab:
        tab = RepoTab(self._settings, self)
        tab.title_changed.connect(lambda title, t=tab: self._on_tab_title_changed(t, title))
        tab.status_changed.connect(self._status_bar.showMessage)

        idx = self._tabs.addTab(tab, _NEW_TAB_LABEL)
        self._tabs.setCurrentIndex(idx)

        if repo_path:
            tab.open_repo(repo_path)

        return tab

    def _close_current_tab(self) -> None:
        self._on_close_tab(self._tabs.currentIndex())

    def _on_close_tab(self, index: int) -> None:
        if self._tabs.count() <= 1:
            return  # always keep at least one tab
        tab = self._tabs.widget(index)
        if isinstance(tab, RepoTab):
            tab.cancel_scan()
        self._tabs.removeTab(index)

    def _on_tab_changed(self, index: int) -> None:
        tab = self._tabs.widget(index)
        if isinstance(tab, RepoTab) and tab.current_repo_path():
            self._status_bar.showMessage(f"Aktif repo: {tab.current_repo_path()}")
        else:
            self._status_bar.showMessage("Hazır — Bir repo seçin ve 'Tara' butonuna tıklayın.")

    def _on_tab_title_changed(self, tab: RepoTab, title: str) -> None:
        idx = self._tabs.indexOf(tab)
        if idx >= 0:
            self._tabs.setTabText(idx, title)
            path = tab.current_repo_path()
            if path:
                self._tabs.setTabToolTip(idx, path)

    def _current_tab(self) -> RepoTab | None:
        w = self._tabs.currentWidget()
        return w if isinstance(w, RepoTab) else None

    # ── State persistence ─────────────────────────────────────────────────────

    def _restore_state(self) -> None:
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)

        geom = qs.value("mainwindow/geometry")
        if isinstance(geom, QByteArray):
            self.restoreGeometry(geom)

        paths = qs.value("mainwindow/open_repos", [])
        if isinstance(paths, str):
            paths = [paths]
        if paths:
            # Replace the default empty tab with the first repo
            first_tab = self._current_tab()
            if first_tab:
                first_tab.open_repo(paths[0])
            for path in paths[1:]:
                self._add_tab(repo_path=path)

    def closeEvent(self, event) -> None:
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        qs.setValue("mainwindow/geometry", self.saveGeometry())

        open_repos = []
        for i in range(self._tabs.count()):
            tab = self._tabs.widget(i)
            if isinstance(tab, RepoTab) and tab.current_repo_path():
                open_repos.append(tab.current_repo_path())
                tab.cancel_scan()

        qs.setValue("mainwindow/open_repos", open_repos)
        super().closeEvent(event)

    # ── Toolbar slots ─────────────────────────────────────────────────────────

    def _on_open_settings(self) -> None:
        from gitbroom.ui.widgets.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self._settings, self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()

    def _on_settings_changed(self, new_settings: object) -> None:
        self._settings = new_settings  # type: ignore[assignment]
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            self._theme.apply(app, self._settings.theme)  # type: ignore[arg-type]
        # Propagate new settings to all open tabs
        for i in range(self._tabs.count()):
            tab = self._tabs.widget(i)
            if isinstance(tab, RepoTab):
                tab.reload_settings(self._settings)  # type: ignore[arg-type]

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "GitBroom Hakkında",
            "<b>GitBroom v0.1.0</b><br><br>"
            "Git branch temizleme aracı.<br><br>"
            "Teknoloji: Python 3.11 · PyQt6 · gitpython<br>"
            "Lisans: MIT",
        )

    def _on_toggle_theme(self) -> None:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            next_theme = self._theme.toggle(app)  # type: ignore[arg-type]
            self._settings.theme = next_theme
            icon_text = "☀️" if next_theme == "light" else "🌙"
            self._btn_theme.setText(icon_text)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fetch_git_user_info() -> tuple[str, str]:
        try:
            name = subprocess.run(
                ["git", "config", "user.name"], capture_output=True, text=True, timeout=3
            ).stdout.strip()
            email = subprocess.run(
                ["git", "config", "user.email"], capture_output=True, text=True, timeout=3
            ).stdout.strip()
            return name, email
        except Exception:
            return "", ""
