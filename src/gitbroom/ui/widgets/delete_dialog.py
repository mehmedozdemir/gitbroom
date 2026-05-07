from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gitbroom.core.models import AppSettings, BranchInfo

_COUNTDOWN_SECS = 2


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
        self.setWindowTitle("⚠️  Branch Silme Onayı")
        self.setMinimumWidth(480)
        self._build_ui()
        self._start_countdown()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Branch list
        layout.addWidget(QLabel("<b>Şu branch'ler silinecek:</b>"))
        for b in self._branches:
            layout.addWidget(self._branch_row(b))

        layout.addWidget(self._hline())

        # Options
        layout.addWidget(QLabel("<b>Silme seçenekleri:</b>"))

        has_local = any(b.is_local for b in self._branches)
        has_remote = any(b.is_remote for b in self._branches)

        self._chk_local = QCheckBox("Local branch'leri sil")
        self._chk_local.setChecked(has_local)
        layout.addWidget(self._chk_local)

        self._chk_remote = QCheckBox("Remote branch'leri sil")
        self._chk_remote.setChecked(has_remote)
        layout.addWidget(self._chk_remote)

        self._chk_backup = QCheckBox("Silmeden önce backup tag oluştur")
        self._chk_backup.setChecked(self._settings.create_backup_tag)
        layout.addWidget(self._chk_backup)

        layout.addWidget(self._hline())

        # Warning
        warning = QLabel("⚠️  Bu işlem geri alınamaz!\n(Backup tag oluşturulursa kurtarılabilir.)")
        warning.setStyleSheet("color: #fab387;")
        layout.addWidget(warning)

        layout.addWidget(self._hline())

        # Buttons
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()

        self._btn_cancel = QPushButton("İptal")
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)

        self._btn_delete = QPushButton(f"Sil ({len(self._branches)} branch) — {self._countdown}s")
        self._btn_delete.setObjectName("dangerButton")
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._on_confirm)
        btn_layout.addWidget(self._btn_delete)

        layout.addWidget(btn_row)

    def _branch_row(self, b: BranchInfo) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 0, 0, 0)

        label = QLabel(f"{b.risk_score.icon}  <b>{b.name}</b>")
        label.setTextFormat(Qt.TextFormat.RichText)

        loc_parts = []
        if b.is_local:
            loc_parts.append("local")
        if b.is_remote:
            loc_parts.append("remote")
        loc_label = QLabel(f"({' + '.join(loc_parts)})")
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
        from gitbroom.core.cleaner import SafeDeleter
        from gitbroom.core.repo import RepoManager

        try:
            repo = RepoManager().load(self._repo_path)
            deleter = SafeDeleter()
            results = deleter.delete_branches(
                [b.name for b in self._branches],
                repo,
                delete_local=self._chk_local.isChecked(),
                delete_remote=self._chk_remote.isChecked(),
                create_backup=self._chk_backup.isChecked(),
            )

            errors = [e for r in results for e in r.errors]
            deleted = sum(1 for r in results if r.local_deleted or r.remote_deleted)

            self._deletion_results = results
            if errors:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "Kısmi Hata",
                    f"{deleted} branch silindi.\n\nHatalar:\n" + "\n".join(errors)
                )
            self.accept()

        except Exception as exc:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Hata", str(exc))

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
