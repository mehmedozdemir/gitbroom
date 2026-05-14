from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gitbroom.core.models import AppSettings, BranchInfo
from gitbroom.ui.theme.icons import icon

_COUNTDOWN_SECS = 2


class _DeleteWorker(QThread):
    branch_done = pyqtSignal(str, bool, str)  # name, success, message
    all_done = pyqtSignal()

    def __init__(
        self,
        branches: list[str],
        repo_path: str,
        delete_local: bool,
        delete_remote: bool,
        create_backup: bool,
        force_local: bool,
    ) -> None:
        super().__init__()
        self._branches = branches
        self._repo_path = repo_path
        self._delete_local = delete_local
        self._delete_remote = delete_remote
        self._create_backup = create_backup
        self._force_local = force_local
        self.results: list = []

    def run(self) -> None:
        from gitbroom.core.cleaner import SafeDeleter
        from gitbroom.core.repo import RepoManager

        try:
            repo = RepoManager().load(self._repo_path)
        except Exception as exc:
            self.branch_done.emit("", False, f"Repo yüklenemedi: {exc}")
            self.all_done.emit()
            return

        deleter = SafeDeleter()
        for name in self._branches:
            try:
                results = deleter.delete_branches(
                    [name],
                    repo,
                    delete_local=self._delete_local,
                    delete_remote=self._delete_remote,
                    create_backup=self._create_backup,
                    force_local=self._force_local,
                )
                r = results[0]
                self.results.append(r)
                if r.errors:
                    self.branch_done.emit(name, False, "; ".join(r.errors))
                else:
                    parts = []
                    if r.local_deleted:
                        parts.append("local")
                    if r.remote_deleted:
                        parts.append("remote")
                    if r.backup_tag:
                        parts.append(f"yedek: {r.backup_tag}")
                    self.branch_done.emit(name, True, ", ".join(parts) if parts else "işlendi")
            except Exception as exc:
                self.branch_done.emit(name, False, str(exc))

        self.all_done.emit()


class DeleteDialog(QDialog):
    def __init__(
        self,
        branches: list[BranchInfo],
        repo_path: str,
        settings: AppSettings,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._branches = branches
        self._repo_path = repo_path
        self._settings = settings
        self._deletion_results: list = []
        self._countdown = _COUNTDOWN_SECS
        self._worker: _DeleteWorker | None = None
        self._completed = 0
        self.setWindowTitle("⚠️  Branch Silme Onayı")
        self.setMinimumWidth(520)
        self._build_ui()
        self._start_countdown()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # Branch list in a scroll area so long lists don't overflow the screen
        root.addWidget(QLabel(f"<b>Şu {len(self._branches)} branch silinecek:</b>"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(220)
        scroll.setFrameShape(QFrame.Shape.StyledPanel)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(2)
        inner_layout.setContentsMargins(4, 4, 4, 4)
        for b in self._branches:
            inner_layout.addWidget(self._branch_row(b))
        inner_layout.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        root.addWidget(self._hline())

        # Options section — hidden while deletion runs
        self._options_widget = QWidget()
        opt_layout = QVBoxLayout(self._options_widget)
        opt_layout.setContentsMargins(0, 0, 0, 0)
        opt_layout.setSpacing(6)

        opt_layout.addWidget(QLabel("<b>Silme seçenekleri:</b>"))

        has_local = any(b.is_local for b in self._branches)
        has_remote = any(b.is_remote for b in self._branches)

        self._chk_local = QCheckBox("Local branch'leri sil")
        self._chk_local.setChecked(has_local)
        self._chk_remote = QCheckBox("Remote branch'leri sil")
        self._chk_remote.setChecked(has_remote)
        self._chk_backup = QCheckBox("Silmeden önce backup tag oluştur")
        self._chk_backup.setChecked(self._settings.create_backup_tag)

        self._chk_force = QCheckBox("Force delete (squash/rebase merge'lerde gerekli)")
        self._chk_force.setChecked(True)

        opt_layout.addWidget(self._chk_local)
        opt_layout.addWidget(self._chk_remote)
        opt_layout.addWidget(self._chk_backup)
        opt_layout.addWidget(self._chk_force)

        warning = QLabel("⚠️  Bu işlem geri alınamaz!\n(Backup tag oluşturulursa kurtarılabilir.)")
        warning.setStyleSheet("color: #fab387;")
        opt_layout.addWidget(warning)

        root.addWidget(self._options_widget)

        # Progress section — shown only during / after deletion
        self._progress_widget = QWidget()
        prog_layout = QVBoxLayout(self._progress_widget)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(6)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, len(self._branches))
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        prog_layout.addWidget(self._progress_bar)

        self._log_output = QPlainTextEdit()
        self._log_output.setReadOnly(True)
        self._log_output.setMaximumHeight(160)
        self._log_output.setMinimumHeight(80)
        prog_layout.addWidget(self._log_output)

        self._progress_widget.setVisible(False)
        root.addWidget(self._progress_widget)

        root.addWidget(self._hline())

        # Buttons
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()

        self._btn_cancel = QPushButton("İptal")
        self._btn_cancel.setIcon(icon("cancel"))
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)

        self._btn_delete = QPushButton(
            f"Sil ({len(self._branches)} branch) — {self._countdown}s"
        )
        self._btn_delete.setIcon(icon("trash"))
        self._btn_delete.setObjectName("dangerButton")
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._on_confirm)
        btn_layout.addWidget(self._btn_delete)

        root.addWidget(btn_row)

    def _branch_row(self, b: BranchInfo) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 0, 0, 0)

        label = QLabel(f"{b.risk_score.icon}  <b>{b.name}</b>")
        label.setTextFormat(Qt.TextFormat.RichText)

        parts = []
        if b.is_local:
            parts.append("local")
        if b.is_remote:
            parts.append("remote")
        loc_label = QLabel(f"({' + '.join(parts)})")
        loc_label.setStyleSheet("color: #a6adc8; font-size: 12px;")

        layout.addWidget(label)
        layout.addWidget(loc_label)
        layout.addStretch()
        return row

    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def _start_countdown(self) -> None:
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._countdown -= 1
        if self._countdown <= 0:
            self._timer.stop()
            self._btn_delete.setEnabled(True)
            self._btn_delete.setText(f"Sil ({len(self._branches)} branch)")
        else:
            self._btn_delete.setText(
                f"Sil ({len(self._branches)} branch) — {self._countdown}s"
            )

    def _on_confirm(self) -> None:
        # Capture checkbox state before hiding the options widget
        delete_local = self._chk_local.isChecked()
        delete_remote = self._chk_remote.isChecked()
        create_backup = self._chk_backup.isChecked()
        force_local = self._chk_force.isChecked()

        self._timer.stop()
        self._options_widget.setVisible(False)
        self._progress_widget.setVisible(True)
        self._btn_delete.setVisible(False)
        self._btn_cancel.setEnabled(False)

        self._worker = _DeleteWorker(
            branches=[b.name for b in self._branches],
            repo_path=self._repo_path,
            delete_local=delete_local,
            delete_remote=delete_remote,
            create_backup=create_backup,
            force_local=force_local,
        )
        self._worker.branch_done.connect(self._on_branch_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_branch_done(self, name: str, success: bool, message: str) -> None:
        self._completed += 1
        self._progress_bar.setValue(self._completed)
        self._progress_bar.setFormat(f"{self._completed} / {len(self._branches)}")
        if name:
            icon = "✓" if success else "✗"
            self._log_output.appendPlainText(f"{icon}  {name}  —  {message}")
        else:
            self._log_output.appendPlainText(f"⚠️  {message}")

    def _on_all_done(self) -> None:
        assert self._worker is not None
        self._deletion_results = self._worker.results
        errors = [e for r in self._deletion_results for e in r.errors]
        deleted = sum(1 for r in self._deletion_results if r.local_deleted or r.remote_deleted)

        if errors:
            summary = f"Tamamlandı: {deleted}/{len(self._branches)} silindi, {len(errors)} hata."
        else:
            summary = f"Tamamlandı: {deleted}/{len(self._branches)} branch başarıyla silindi."
        self._log_output.appendPlainText(f"\n{summary}")

        self._btn_cancel.setText("Kapat")
        self._btn_cancel.setIcon(icon("close"))
        self._btn_cancel.setEnabled(True)
        self._btn_cancel.clicked.disconnect()
        self._btn_cancel.clicked.connect(self.accept)

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            event.ignore()
        else:
            super().closeEvent(event)

    # Public accessors (used by tests)
    def delete_local(self) -> bool:
        return self._chk_local.isChecked()

    def delete_remote(self) -> bool:
        return self._chk_remote.isChecked()

    def create_backup(self) -> bool:
        return self._chk_backup.isChecked()

    @property
    def deletion_results(self) -> list:
        return self._deletion_results
