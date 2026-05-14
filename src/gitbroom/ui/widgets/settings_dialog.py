from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gitbroom.core.models import AppSettings
from gitbroom.config.settings import save_settings
from gitbroom.ui.theme.icons import icon


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
        tabs.addTab(self._build_protected_tab(), "Korumalı Branch'ler")
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
        self._btn_test.setIcon(icon("test"))
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

        self._chk_rebase = QCheckBox(
            "Rebase merge tespiti (yavaş — büyük repolar için önerilmez)"
        )
        self._chk_rebase.setChecked(self._settings.enable_rebase_detection)
        form.addRow(self._chk_rebase)

        return tab

    def _build_protected_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        note = QLabel(
            "Bu listedeki branch'ler listede gösterilmez ve silinemez.\n"
            "Wildcard desteklenmez — tam branch adı girilmelidir."
        )
        note.setStyleSheet("color: #a6adc8; font-size: 12px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._protected_list = QListWidget()
        self._protected_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        for name in self._settings.protected_branches:
            self._protected_list.addItem(name)
        layout.addWidget(self._protected_list)

        add_row = QWidget()
        add_layout = QHBoxLayout(add_row)
        add_layout.setContentsMargins(0, 0, 0, 0)
        self._protected_input = QLineEdit()
        self._protected_input.setPlaceholderText("Branch adı ekle...")
        self._protected_input.returnPressed.connect(self._on_add_protected)
        btn_add = QPushButton("Ekle")
        btn_add.setIcon(icon("add"))
        btn_add.clicked.connect(self._on_add_protected)
        add_layout.addWidget(self._protected_input)
        add_layout.addWidget(btn_add)
        layout.addWidget(add_row)

        btn_remove = QPushButton("Seçileni Kaldır")
        btn_remove.setIcon(icon("remove"))
        btn_remove.clicked.connect(self._on_remove_protected)
        layout.addWidget(btn_remove)

        return tab

    def _on_add_protected(self) -> None:
        name = self._protected_input.text().strip()
        if not name:
            return
        existing = [
            self._protected_list.item(i).text()
            for i in range(self._protected_list.count())
        ]
        if name not in existing:
            self._protected_list.addItem(name)
        self._protected_input.clear()

    def _on_remove_protected(self) -> None:
        for item in self._protected_list.selectedItems():
            self._protected_list.takeItem(self._protected_list.row(item))

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        protected = [
            self._protected_list.item(i).text()
            for i in range(self._protected_list.count())
        ]
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
            enable_rebase_detection=self._chk_rebase.isChecked(),
            protected_branches=protected,
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
