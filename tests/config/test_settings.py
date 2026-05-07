import os
from pathlib import Path

import pytest

from gitbroom.config.settings import load_settings, save_settings
from gitbroom.core.models import AppSettings


class TestSettingsLoadDefaults:
    def test_returns_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        monkeypatch.delenv("GITBROOM_GITLAB_TOKEN", raising=False)
        settings = load_settings()
        assert settings.default_branch == "main"
        assert settings.stale_days_green == 90
        assert settings.theme == "dark"
        assert settings.gitlab_enabled is False

    def test_gitlab_token_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        monkeypatch.setenv("GITBROOM_GITLAB_TOKEN", "glpat-test-token")
        settings = load_settings()
        assert settings.gitlab_token == "glpat-test-token"
        assert settings.gitlab_enabled is True


class TestSettingsSave:
    def test_creates_toml_file(self, tmp_path):
        settings = AppSettings(default_branch="develop", theme="light")
        target = tmp_path / "config.toml"
        save_settings(settings, path=target)
        assert target.exists()
        content = target.read_text()
        assert "develop" in content
        assert "light" in content

    def test_creates_parent_directory(self, tmp_path):
        nested = tmp_path / "nested" / "dir"
        target = nested / "config.toml"
        save_settings(AppSettings(), path=target)
        assert target.exists()


class TestSettingsRoundTrip:
    def test_save_then_load_preserves_values(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        monkeypatch.delenv("GITBROOM_GITLAB_TOKEN", raising=False)

        original = AppSettings(
            default_branch="develop",
            stale_days_green=60,
            stale_days_yellow=20,
            stale_days_red=7,
            theme="light",
            language="en",
            gitlab_enabled=True,
            gitlab_url="https://gitlab.example.com",
            gitlab_token="glpat-secret",
            create_backup_tag=False,
            confirm_remote_delete=False,
            show_merged_by_default=False,
        )
        save_settings(original, path=tmp_path / "config.toml")
        loaded = load_settings()

        assert loaded.default_branch == "develop"
        assert loaded.stale_days_green == 60
        assert loaded.stale_days_yellow == 20
        assert loaded.stale_days_red == 7
        assert loaded.theme == "light"
        assert loaded.language == "en"
        assert loaded.gitlab_enabled is True
        assert loaded.gitlab_url == "https://gitlab.example.com"
        assert loaded.gitlab_token == "glpat-secret"
        assert loaded.create_backup_tag is False
        assert loaded.confirm_remote_delete is False
        assert loaded.show_merged_by_default is False

    def test_env_token_overrides_file_token(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        monkeypatch.setenv("GITBROOM_GITLAB_TOKEN", "env-token")

        original = AppSettings(gitlab_token="file-token")
        save_settings(original, path=tmp_path / "config.toml")
        loaded = load_settings()

        assert loaded.gitlab_token == "env-token"
