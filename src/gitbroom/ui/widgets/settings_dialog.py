from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gitbroom.core.models import AppSettings
from gitbroom.config.settings import save_settings


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal(object)  # AppSettings

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Ayarlar")
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "Genel")
        tabs.addTab(self._build_gitlab_tab(), "GitLab")
        tabs.addTab(self._build_behavior_tab(), "Davranış")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── Tabs ─────────────────────────────────────────────────────────────────

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self._default_branch = QLineEdit(self._settings.default_branch)
        form.addRow("Default Branch:", self._default_branch)

        self._stale_green = QSpinBox()
        self._stale_green.setRange(1, 3650)
        self._stale_green.setValue(self._settings.stale_days_green)
        self._stale_green.setSuffix(" gün")
        form.addRow("🟢 Güvenli Sil eşiği:", self._stale_green)

        self._stale_yellow = QSpinBox()
        self._stale_yellow.setRange(1, 3650)
        self._stale_yellow.setValue(self._settings.stale_days_yellow)
        self._stale_yellow.setSuffix(" gün")
        form.addRow("🟡 Gözden Geçir eşiği:", self._stale_yellow)

        self._stale_red = QSpinBox()
        self._stale_red.setRange(1, 365)
        self._stale_red.setValue(self._settings.stale_days_red)
        self._stale_red.setSuffix(" gün")
        form.addRow("🔴 Dokunma eşiği:", self._stale_red)

        return tab

    def _build_gitlab_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self._gitlab_enabled = QCheckBox("GitLab entegrasyonunu etkinleştir")
        self._gitlab_enabled.setChecked(self._settings.gitlab_enabled)
        form.addRow(self._gitlab_enabled)

        self._gitlab_url = QLineEdit(self._settings.gitlab_url)
        form.addRow("GitLab URL:", self._gitlab_url)

        self._gitlab_token = QLineEdit(self._settings.gitlab_token)
        self._gitlab_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._gitlab_token.setPlaceholderText("glpat-xxxxxxxxxxxx veya GITBROOM_GITLAB_TOKEN env var")
        form.addRow("Access Token:", self._gitlab_token)

        test_row = QWidget()
        test_layout = QHBoxLayout(test_row)
        test_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_test = QPushButton("Bağlantıyı Test Et")
        self._btn_test.clicked.connect(self._on_test_gitlab)
        self._test_result = QLabel("")
        test_layout.addWidget(self._btn_test)
        test_layout.addWidget(self._test_result)
        test_layout.addStretch()
        form.addRow(test_row)

        return tab

    def _build_behavior_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self._chk_backup = QCheckBox("Silmeden önce otomatik backup tag oluştur")
        self._chk_backup.setChecked(self._settings.create_backup_tag)
        form.addRow(self._chk_backup)

        self._chk_remote_confirm = QCheckBox("Remote silme işlemini ayrıca onayla")
        self._chk_remote_confirm.setChecked(self._settings.confirm_remote_delete)
        form.addRow(self._chk_remote_confirm)

        self._chk_show_merged = QCheckBox("Varsayılan olarak merge edilmişleri göster")
        self._chk_show_merged.setChecked(self._settings.show_merged_by_default)
        form.addRow(self._chk_show_merged)

        return tab

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        updated = AppSettings(
            default_branch=self._default_branch.text().strip() or "main",
            stale_days_green=self._stale_green.value(),
            stale_days_yellow=self._stale_yellow.value(),
            stale_days_red=self._stale_red.value(),
            theme=self._settings.theme,
            language=self._settings.language,
            gitlab_enabled=self._gitlab_enabled.isChecked(),
            gitlab_url=self._gitlab_url.text().strip(),
            gitlab_token=self._gitlab_token.text().strip(),
            create_backup_tag=self._chk_backup.isChecked(),
            confirm_remote_delete=self._chk_remote_confirm.isChecked(),
            show_merged_by_default=self._chk_show_merged.isChecked(),
        )
        try:
            save_settings(updated)
        except Exception as e:
            QMessageBox.warning(self, "Kayıt Hatası", str(e))
            return

        self.settings_changed.emit(updated)
        self.accept()

    def _on_test_gitlab(self) -> None:
        url = self._gitlab_url.text().strip()
        token = self._gitlab_token.text().strip()
        if not url or not token:
            self._test_result.setText("⚠️ URL ve token gerekli")
            return

        self._test_result.setText("Bağlanıyor…")
        self._btn_test.setEnabled(False)
        try:
            import gitlab  # type: ignore
            gl = gitlab.Gitlab(url, private_token=token)
            gl.auth()
            self._test_result.setText("✅ Bağlantı başarılı")
        except Exception as e:
            self._test_result.setText(f"❌ Hata: {e}")
        finally:
            self._btn_test.setEnabled(True)
