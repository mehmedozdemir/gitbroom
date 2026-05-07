from __future__ import annotations

import os
import tomllib
from pathlib import Path

from gitbroom.core.models import AppSettings

_CONFIG_PATH = Path.home() / ".gitbroom" / "config.toml"


def _config_path() -> Path:
    env_dir = os.environ.get("GITBROOM_CONFIG_DIR")
    if env_dir:
        return Path(env_dir) / "config.toml"
    return _CONFIG_PATH


_SECTION_PREFIXES: dict[str, str] = {
    "general": "",
    "gitlab": "gitlab_",
    "behavior": "",
}


def _flatten(data: dict) -> dict:
    """Flatten nested TOML sections into AppSettings field names."""
    result: dict = {}
    for section_name, section_data in data.items():
        if not isinstance(section_data, dict):
            continue
        prefix = _SECTION_PREFIXES.get(section_name, f"{section_name}_")
        for key, value in section_data.items():
            result[f"{prefix}{key}"] = value
    return result


def load_settings() -> AppSettings:
    """Load settings from TOML; returns defaults if file doesn't exist."""
    path = _config_path()
    if not path.exists():
        settings = AppSettings()
        # Inject GitLab token from env if present
        token = os.environ.get("GITBROOM_GITLAB_TOKEN", "")
        if token:
            settings.gitlab_token = token
            settings.gitlab_enabled = True
        return settings

    with open(path, "rb") as f:
        data = tomllib.load(f)

    flat = _flatten(data)
    token = os.environ.get("GITBROOM_GITLAB_TOKEN", flat.get("gitlab_token", ""))
    if token:
        flat["gitlab_token"] = token

    valid_fields = AppSettings.__dataclass_fields__.keys()
    filtered = {k: v for k, v in flat.items() if k in valid_fields}
    return AppSettings(**filtered)


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    """Persist settings to TOML file."""
    target = path or _config_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "[general]\n",
        f'default_branch = "{settings.default_branch}"\n',
        f"stale_days_green = {settings.stale_days_green}\n",
        f"stale_days_yellow = {settings.stale_days_yellow}\n",
        f"stale_days_red = {settings.stale_days_red}\n",
        f'theme = "{settings.theme}"\n',
        f'language = "{settings.language}"\n',
        "\n",
        "[gitlab]\n",
        f"enabled = {str(settings.gitlab_enabled).lower()}\n",
        f'url = "{settings.gitlab_url}"\n',
        f'token = "{settings.gitlab_token}"\n',
        "\n",
        "[behavior]\n",
        f"create_backup_tag = {str(settings.create_backup_tag).lower()}\n",
        f"confirm_remote_delete = {str(settings.confirm_remote_delete).lower()}\n",
        f"show_merged_by_default = {str(settings.show_merged_by_default).lower()}\n",
        f"enable_rebase_detection = {str(settings.enable_rebase_detection).lower()}\n",
    ]
    target.write_text("".join(lines), encoding="utf-8")
