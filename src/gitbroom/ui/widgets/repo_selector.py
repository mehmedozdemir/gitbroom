from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from gitbroom.core.models import AppSettings

_MAX_RECENT = 10


class RepoSelector(QWidget):
    repo_changed = pyqtSignal(str)

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._recent: list[str] = list(getattr(settings, "recent_repos", []))
        self._build_ui()
        self._load_last_repo()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Repo:"))

        self._combo = QComboBox()
        self._combo.setEditable(True)
        self._combo.setMinimumWidth(400)
        self._combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._combo.addItems(self._recent)
        layout.addWidget(self._combo, stretch=1)

        self._btn_browse = QPushButton("Klasör Seç")
        self._btn_browse.clicked.connect(self._on_browse)
        layout.addWidget(self._btn_browse)

        self._btn_scan = QPushButton("Tara")
        self._btn_scan.setObjectName("primaryButton")
        self._btn_scan.setShortcut("Ctrl+R")
        self._btn_scan.clicked.connect(self._on_scan)
        layout.addWidget(self._btn_scan)

    def _load_last_repo(self) -> None:
        if self._recent:
            self._combo.setCurrentText(self._recent[0])

    def _on_browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Git Repo Seç")
        if path:
            self._set_repo(path)

    def _on_scan(self) -> None:
        path = self._combo.currentText().strip()
        if path:
            self._set_repo(path)

    def _set_repo(self, path: str) -> None:
        if path in self._recent:
            self._recent.remove(path)
        self._recent.insert(0, path)
        self._recent = self._recent[:_MAX_RECENT]

        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItems(self._recent)
        self._combo.setCurrentText(path)
        self._combo.blockSignals(False)

        self.repo_changed.emit(path)

    def current_path(self) -> str:
        return self._combo.currentText().strip()
