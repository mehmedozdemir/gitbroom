from __future__ import annotations

import logging

from PyQt6.QtCore import QByteArray, QSettings, Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from gitbroom.core.models import AppSettings
from gitbroom.ui.theme.icons import icon
from gitbroom.ui.theme.theme import ThemeManager
from gitbroom.ui.widgets.branch_detail import BranchDetailPanel
from gitbroom.ui.widgets.branch_table import BranchTable
from gitbroom.ui.widgets.repo_selector import RepoSelector

logger = logging.getLogger(__name__)

_QSETTINGS_ORG = "GitBroom"
_QSETTINGS_APP = "GitBroom"


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._settings = settings
        self._theme = theme_manager
        self._repo_path: str | None = None
        self._worker = None
        self._setup_window()
        self._build_ui()
        self._restore_state()

    def _setup_window(self) -> None:
        self.setWindowTitle("GitBroom — Git Branch Temizleyici")
        self.resize(1200, 750)
        self.setMinimumSize(900, 600)
        self._git_user_name, self._git_user_email = self._fetch_git_user_info()

    def _build_ui(self) -> None:
        self._build_toolbar()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self._repo_selector = RepoSelector(self._settings)
        self._repo_selector.repo_changed.connect(self._on_repo_changed)
        root.addWidget(self._repo_selector)

        root.addWidget(self._build_filter_bar())
        root.addWidget(self._build_progress_bar())

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)

        self._branch_table = BranchTable()
        self._branch_table.selection_changed.connect(self._on_selection_changed)
        self._branch_table.delete_requested.connect(self._on_delete_requested)
        self._branch_table.branch_selected.connect(self._on_branch_selected)
        self._splitter.addWidget(self._branch_table)

        self._detail_panel = BranchDetailPanel()
        self._splitter.addWidget(self._detail_panel)

        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)

        root.addWidget(self._splitter, stretch=1)
        root.addWidget(self._build_action_bar())
        self._build_status_bar()

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

    def _build_filter_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._btn_filter_all = QPushButton("≡  Hepsi")
        self._btn_filter_mine = QPushButton("👤  Benim")
        self._btn_filter_merged = QPushButton("✓  Merged")
        self._btn_filter_stale = QPushButton("⏱  Stale")

        for btn in (
            self._btn_filter_all,
            self._btn_filter_mine,
            self._btn_filter_merged,
            self._btn_filter_stale,
        ):
            btn.setCheckable(True)
            layout.addWidget(btn)

        self._btn_filter_all.setChecked(True)
        self._btn_filter_all.clicked.connect(lambda: self._apply_filter("all"))
        self._btn_filter_mine.clicked.connect(lambda: self._apply_filter("mine"))
        self._btn_filter_merged.clicked.connect(lambda: self._apply_filter("merged"))
        self._btn_filter_stale.clicked.connect(lambda: self._apply_filter("stale"))

        layout.addStretch()

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Branch adı veya yazar ara...")
        self._search_box.setFixedWidth(240)
        self._search_box.textChanged.connect(self._on_search)
        layout.addWidget(QLabel("🔍"))
        layout.addWidget(self._search_box)
        return bar

    def _build_progress_bar(self) -> QProgressBar:
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        return self._progress

    def _build_action_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 4, 0, 0)

        self._selection_label = QLabel("Seçili: 0 branch")
        layout.addWidget(self._selection_label)

        self._btn_select_all = QPushButton("Tümünü Seç")
        self._btn_select_all.setIcon(icon("check_all"))
        self._btn_select_all.clicked.connect(lambda: self._branch_table.check_all(True))
        layout.addWidget(self._btn_select_all)

        self._btn_deselect_all = QPushButton("Seçimi Temizle")
        self._btn_deselect_all.setIcon(icon("uncheck"))
        self._btn_deselect_all.setShortcut("Escape")
        self._btn_deselect_all.clicked.connect(lambda: self._branch_table.check_all(False))
        layout.addWidget(self._btn_deselect_all)

        layout.addStretch()

        self._btn_delete = QPushButton("Seçilileri Sil")
        self._btn_delete.setIcon(icon("trash"))
        self._btn_delete.setObjectName("dangerButton")
        self._btn_delete.setEnabled(False)
        self._btn_delete.setShortcut("Delete")
        self._btn_delete.clicked.connect(self._on_delete_selected)
        layout.addWidget(self._btn_delete)
        return bar

    def _build_status_bar(self) -> None:
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Hazır — Bir repo seçin ve 'Tara' butonuna tıklayın.")

    # ── State persistence ────────────────────────────────────────────────────

    def _restore_state(self) -> None:
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        geom = qs.value("mainwindow/geometry")
        if isinstance(geom, QByteArray):
            self.restoreGeometry(geom)
        splitter_state = qs.value("mainwindow/splitter")
        if isinstance(splitter_state, QByteArray):
            self._splitter.restoreState(splitter_state)

    def closeEvent(self, event) -> None:
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        qs.setValue("mainwindow/geometry", self.saveGeometry())
        qs.setValue("mainwindow/splitter", self._splitter.saveState())
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
        super().closeEvent(event)

    # ── Slots ────────────────────────────────────────────────────────────────

    @pyqtSlot(str)
    def _on_repo_changed(self, path: str) -> None:
        self._repo_path = path
        self._detail_panel.set_repo_path(path)
        self._detail_panel.clear()
        self._start_scan(path)

    def _start_scan(self, path: str) -> None:
        from gitbroom.ui.workers import RepoScanWorker

        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()

        self._branch_table.clear()
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._status_bar.showMessage(f"Taranıyor: {path} …")
        self._btn_delete.setEnabled(False)

        self._worker = RepoScanWorker(path, self._settings)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.branch_found.connect(self._on_branch_found)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.error.connect(self._on_scan_error)
        self._worker.start()

    @pyqtSlot(int, int, str)
    def _on_scan_progress(self, current: int, total: int, name: str) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(current)
        self._status_bar.showMessage(f"Analiz ediliyor: {name} ({current}/{total})")

    @pyqtSlot(object)
    def _on_branch_found(self, branch: object) -> None:
        from gitbroom.core.models import BranchInfo
        b = branch  # type: ignore[assignment]
        if isinstance(b, BranchInfo) and b.name in self._settings.protected_branches:
            return
        self._branch_table.add_branch(branch)  # type: ignore[arg-type]

    @pyqtSlot(list)
    def _on_scan_finished(self, branches: list) -> None:
        self._progress.setVisible(False)
        n = len(branches)
        self._status_bar.showMessage(f"Tamamlandı — {n} branch bulundu.")
        logger.info("Scan complete: %d branches in %s", n, self._repo_path)

    @pyqtSlot(str)
    def _on_scan_error(self, message: str) -> None:
        self._progress.setVisible(False)
        self._status_bar.showMessage(f"Hata: {message}")
        logger.error("Scan error: %s", message)
        QMessageBox.warning(self, "Tarama Hatası", message)

    @pyqtSlot(int)
    def _on_selection_changed(self, count: int) -> None:
        self._selection_label.setText(f"Seçili: {count} branch")
        self._btn_delete.setEnabled(count > 0)

    @pyqtSlot(object)
    def _on_branch_selected(self, branch: object) -> None:
        if branch is None:
            self._detail_panel.clear()
        else:
            self._detail_panel.show_branch(branch)  # type: ignore[arg-type]

    @pyqtSlot(list)
    def _on_delete_requested(self, branches: list) -> None:
        self._show_delete_dialog(branches)

    def _on_delete_selected(self) -> None:
        self._show_delete_dialog(self._branch_table.checked_branches())

    def _show_delete_dialog(self, branches: list) -> None:
        if not branches or not self._repo_path:
            return
        from gitbroom.ui.widgets.delete_dialog import DeleteDialog
        dialog = DeleteDialog(branches, self._repo_path, self._settings, self)
        if dialog.exec():
            self._detail_panel.clear()
            deleted_names = {
                r.branch_name
                for r in dialog.deletion_results
                if r.local_deleted or r.remote_deleted
            }
            if deleted_names:
                self._branch_table.remove_branches(deleted_names)
                self._status_bar.showMessage(f"{len(deleted_names)} branch silindi.")

    def _apply_filter(self, mode: str) -> None:
        self._btn_filter_all.setChecked(mode == "all")
        self._btn_filter_mine.setChecked(mode == "mine")
        self._btn_filter_merged.setChecked(mode == "merged")
        self._btn_filter_stale.setChecked(mode == "stale")

        text = self._search_box.text()
        if mode == "merged":
            self._branch_table.apply_filter(text=text, show_merged=True)
        elif mode == "stale":
            self._branch_table.apply_filter(text=text, show_stale=True)
        elif mode == "mine":
            self._branch_table.apply_filter(
                text=text,
                mine_email=self._git_user_email or None,
                mine_name=self._git_user_name or None,
            )
        else:
            self._branch_table.apply_filter(text=text)

    def _on_search(self, text: str) -> None:
        show_merged = True if self._btn_filter_merged.isChecked() else None
        show_stale = True if self._btn_filter_stale.isChecked() else None
        is_mine = self._btn_filter_mine.isChecked()
        self._branch_table.apply_filter(
            text=text,
            show_merged=show_merged,
            show_stale=show_stale,
            mine_email=self._git_user_email or None if is_mine else None,
            mine_name=self._git_user_name or None if is_mine else None,
        )

    def _fetch_git_user_info(self) -> tuple[str, str]:
        try:
            import subprocess
            name = subprocess.run(
                ["git", "config", "user.name"],
                capture_output=True, text=True, timeout=3,
            ).stdout.strip()
            email = subprocess.run(
                ["git", "config", "user.email"],
                capture_output=True, text=True, timeout=3,
            ).stdout.strip()
            return name, email
        except Exception:
            return "", ""

    def _on_open_settings(self) -> None:
        from gitbroom.ui.widgets.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self._settings, self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()

    @pyqtSlot(object)
    def _on_settings_changed(self, new_settings: object) -> None:
        self._settings = new_settings  # type: ignore[assignment]
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            self._theme.apply(app, self._settings.theme)  # type: ignore[arg-type]
        if self._repo_path:
            self._start_scan(self._repo_path)

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "GitBroom Hakkında",
            "<b>GitBroom v0.1.0</b><br><br>"
            "Git branch temizleme aracı.<br><br>"
            "Teknoloji: Python 3.11 · PyQt6 · gitpython<br>"
            "Lisans: MIT",
        )

    @pyqtSlot()
    def _on_toggle_theme(self) -> None:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            next_theme = self._theme.toggle(app)  # type: ignore[arg-type]
            self._settings.theme = next_theme
            icon = "☀️" if next_theme == "light" else "🌙"
            self._btn_theme.setText(icon)
