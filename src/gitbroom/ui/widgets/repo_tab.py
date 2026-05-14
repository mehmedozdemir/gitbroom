from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gitbroom.core.models import AppSettings
from gitbroom.ui.theme.icons import icon
from gitbroom.ui.widgets.branch_detail import BranchDetailPanel
from gitbroom.ui.widgets.branch_table import BranchTable
from gitbroom.ui.widgets.repo_selector import RepoSelector

logger = logging.getLogger(__name__)


class RepoTab(QWidget):
    """Self-contained widget for one repository. Hosts scan, filter, table and detail panel."""

    title_changed = pyqtSignal(str)   # new tab label
    status_changed = pyqtSignal(str)  # forwarded to main status bar

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._repo_path: str | None = None
        self._worker = None
        self._build_ui()

    # ── Public API ────────────────────────────────────────────────────────────

    def open_repo(self, path: str) -> None:
        """Open a repo programmatically (used when restoring session)."""
        self._repo_selector.set_path(path)

    def current_repo_path(self) -> str | None:
        return self._repo_path

    def reload_settings(self, settings: AppSettings) -> None:
        self._settings = settings
        if self._repo_path:
            self._start_scan(self._repo_path)

    def cancel_scan(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 4)
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

        btn_select_all = QPushButton("Tümünü Seç")
        btn_select_all.setIcon(icon("check_all"))
        btn_select_all.clicked.connect(lambda: self._branch_table.check_all(True))
        layout.addWidget(btn_select_all)

        btn_deselect = QPushButton("Seçimi Temizle")
        btn_deselect.setIcon(icon("uncheck"))
        btn_deselect.setShortcut("Escape")
        btn_deselect.clicked.connect(lambda: self._branch_table.check_all(False))
        layout.addWidget(btn_deselect)

        layout.addStretch()

        self._btn_delete = QPushButton("Seçilileri Sil")
        self._btn_delete.setIcon(icon("trash"))
        self._btn_delete.setObjectName("dangerButton")
        self._btn_delete.setEnabled(False)
        self._btn_delete.setShortcut("Delete")
        self._btn_delete.clicked.connect(self._on_delete_selected)
        layout.addWidget(self._btn_delete)
        return bar

    # ── Scan ─────────────────────────────────────────────────────────────────

    def _start_scan(self, path: str) -> None:
        from gitbroom.ui.workers import RepoScanWorker

        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()

        self._branch_table.clear()
        self._detail_panel.clear()
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._btn_delete.setEnabled(False)
        self.status_changed.emit(f"Taranıyor: {path} …")

        self._worker = RepoScanWorker(path, self._settings)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.branch_found.connect(self._on_branch_found)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.error.connect(self._on_scan_error)
        self._worker.start()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_repo_changed(self, path: str) -> None:
        self._repo_path = path
        self._detail_panel.set_repo_path(path)
        folder = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        self.title_changed.emit(folder or path)
        self._start_scan(path)

    def _on_scan_progress(self, current: int, total: int, name: str) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(current)
        self.status_changed.emit(f"Analiz ediliyor: {name} ({current}/{total})")

    def _on_branch_found(self, branch: object) -> None:
        from gitbroom.core.models import BranchInfo
        b = branch  # type: ignore[assignment]
        if isinstance(b, BranchInfo) and b.name in self._settings.protected_branches:
            return
        self._branch_table.add_branch(branch)  # type: ignore[arg-type]

    def _on_scan_finished(self, branches: list) -> None:
        self._progress.setVisible(False)
        n = len(branches)
        self.status_changed.emit(f"Tamamlandı — {n} branch bulundu.")
        logger.info("Scan complete: %d branches in %s", n, self._repo_path)

    def _on_scan_error(self, message: str) -> None:
        from PyQt6.QtWidgets import QMessageBox
        self._progress.setVisible(False)
        self.status_changed.emit(f"Hata: {message}")
        logger.error("Scan error: %s", message)
        QMessageBox.warning(self, "Tarama Hatası", message)

    def _on_selection_changed(self, count: int) -> None:
        self._selection_label.setText(f"Seçili: {count} branch")
        self._btn_delete.setEnabled(count > 0)

    def _on_branch_selected(self, branch: object) -> None:
        if branch is None:
            self._detail_panel.clear()
        else:
            self._detail_panel.show_branch(branch)  # type: ignore[arg-type]

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
                self.status_changed.emit(f"{len(deleted_names)} branch silindi.")

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
            name, email = self._get_git_user_info()
            self._branch_table.apply_filter(
                text=text,
                mine_email=email or None,
                mine_name=name or None,
            )
        else:
            self._branch_table.apply_filter(text=text)

    def _on_search(self, text: str) -> None:
        show_merged = True if self._btn_filter_merged.isChecked() else None
        show_stale = True if self._btn_filter_stale.isChecked() else None
        is_mine = self._btn_filter_mine.isChecked()
        name, email = self._get_git_user_info() if is_mine else ("", "")
        self._branch_table.apply_filter(
            text=text,
            show_merged=show_merged,
            show_stale=show_stale,
            mine_email=email or None if is_mine else None,
            mine_name=name or None if is_mine else None,
        )

    @staticmethod
    def _get_git_user_info() -> tuple[str, str]:
        try:
            import subprocess
            name = subprocess.run(
                ["git", "config", "user.name"], capture_output=True, text=True, timeout=3
            ).stdout.strip()
            email = subprocess.run(
                ["git", "config", "user.email"], capture_output=True, text=True, timeout=3
            ).stdout.strip()
            return name, email
        except Exception:
            return "", ""
