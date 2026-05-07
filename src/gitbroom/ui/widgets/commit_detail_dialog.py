from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gitbroom.ui.widgets.diff_highlighter import DiffHighlighter


_CHANGE_ICONS = {"A": "✚", "D": "✖", "M": "●", "R": "→"}
_CHANGE_COLORS = {"A": "#a6e3a1", "D": "#f38ba8", "M": "#89b4fa", "R": "#f9e2af"}


class CommitDetailDialog(QDialog):
    def __init__(
        self,
        repo_path: str,
        commit_sha: str,
        short_sha: str,
        commit_message: str,
        author: str,
        parent_widget=None,
    ) -> None:
        super().__init__(parent_widget)
        self._repo_path = repo_path
        self._commit_sha = commit_sha
        self._files: list[dict] = []
        self._loader = None

        self.setWindowTitle(f"{short_sha} — {commit_message[:60]}")
        self.resize(1100, 650)
        self.setMinimumSize(800, 500)
        self._build_ui(short_sha, commit_message, author)
        self._load_diff()

    def _build_ui(self, short_sha: str, message: str, author: str) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # Header
        header = QLabel(f"<b>{short_sha}</b>  {message}  <span style='color:#a6adc8'>— {author}</span>")
        header.setTextFormat(Qt.TextFormat.RichText)
        header.setWordWrap(True)
        root.addWidget(header)

        # Splitter: file list (left) | diff viewer (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left — file list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("<b>Değişen Dosyalar</b>"))

        self._file_list = QListWidget()
        self._file_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._file_list.currentRowChanged.connect(self._on_file_selected)
        left_layout.addWidget(self._file_list)
        splitter.addWidget(left)

        # Right — diff viewer
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._diff_label = QLabel("<b>Diff</b>")
        right_layout.addWidget(self._diff_label)

        self._diff_view = QTextEdit()
        self._diff_view.setReadOnly(True)
        font = QFont("Cascadia Code, Consolas, Courier New")
        font.setPointSize(10)
        self._diff_view.setFont(font)
        self._diff_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._highlighter = DiffHighlighter(self._diff_view.document())
        right_layout.addWidget(self._diff_view)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, stretch=1)

        self._status_label = QLabel("Yükleniyor…")
        self._status_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        root.addWidget(self._status_label)

    def closeEvent(self, event) -> None:
        if self._loader and self._loader.isRunning():
            self._loader.diff_loaded.disconnect()
            self._loader.error.disconnect()
            self._loader.quit()
            self._loader.wait(2000)
        super().closeEvent(event)

    def _load_diff(self) -> None:
        from gitbroom.ui.workers import CommitDiffLoader
        self._loader = CommitDiffLoader(self._repo_path, self._commit_sha)
        self._loader.diff_loaded.connect(self._on_diff_loaded)
        self._loader.error.connect(self._on_load_error)
        self._loader.start()

    def _on_diff_loaded(self, files: list) -> None:
        self._files = files
        self._file_list.clear()

        for f in files:
            icon = _CHANGE_ICONS.get(f["change_type"], "●")
            color = _CHANGE_COLORS.get(f["change_type"], "#cdd6f4")
            additions = f["additions"]
            deletions = f["deletions"]
            label = f"{icon}  {f['path']}   +{additions} -{deletions}"
            item = QListWidgetItem(label)
            item.setForeground(Qt.GlobalColor.white)
            from PyQt6.QtGui import QColor
            item.setData(Qt.ItemDataRole.UserRole, color)
            self._file_list.addItem(item)

        count = len(files)
        self._status_label.setText(f"{count} dosya değişti")

        if files:
            self._file_list.setCurrentRow(0)

    def _on_load_error(self, message: str) -> None:
        self._status_label.setText(f"Hata: {message}")

    def _on_file_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._files):
            return
        f = self._files[row]
        self._diff_label.setText(f"<b>{f['path']}</b>  +{f['additions']} -{f['deletions']}")
        diff_text = f["diff_text"]
        if not diff_text.strip():
            diff_text = "(binary dosya veya değişiklik yok)"
        self._diff_view.setPlainText(diff_text)
