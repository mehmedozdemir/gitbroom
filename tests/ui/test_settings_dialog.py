from __future__ import annotations

import pytest

from gitbroom.core.models import AppSettings
from gitbroom.ui.widgets.settings_dialog import SettingsDialog


@pytest.fixture
def default_settings() -> AppSettings:
    return AppSettings()


class TestSettingsDialogInit:
    def test_opens_with_current_values(self, qtbot, default_settings):
        dialog = SettingsDialog(default_settings)
        qtbot.addWidget(dialog)
        assert dialog._default_branch.text() == "main"
        assert dialog._stale_green.value() == 90
        assert dialog._stale_yellow.value() == 30
        assert dialog._stale_red.value() == 14

    def test_gitlab_fields_populated(self, qtbot, default_settings):
        dialog = SettingsDialog(default_settings)
        qtbot.addWidget(dialog)
        assert dialog._gitlab_url.text() == "https://gitlab.com"
        assert not dialog._gitlab_enabled.isChecked()

    def test_behavior_checkboxes(self, qtbot, default_settings):
        dialog = SettingsDialog(default_settings)
        qtbot.addWidget(dialog)
        assert dialog._chk_backup.isChecked()
        assert dialog._chk_remote_confirm.isChecked()
        assert dialog._chk_show_merged.isChecked()


class TestSettingsDialogSave:
    def test_emits_settings_changed_on_save(self, qtbot, tmp_path, monkeypatch, default_settings):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        dialog = SettingsDialog(default_settings)
        qtbot.addWidget(dialog)

        received = []
        dialog.settings_changed.connect(received.append)

        dialog._default_branch.setText("develop")
        dialog._stale_green.setValue(60)
        dialog._on_save()

        assert len(received) == 1
        assert received[0].default_branch == "develop"
        assert received[0].stale_days_green == 60

    def test_empty_default_branch_falls_back_to_main(self, qtbot, tmp_path, monkeypatch, default_settings):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        dialog = SettingsDialog(default_settings)
        qtbot.addWidget(dialog)

        received = []
        dialog.settings_changed.connect(received.append)
        dialog._default_branch.setText("")
        dialog._on_save()

        assert received[0].default_branch == "main"
