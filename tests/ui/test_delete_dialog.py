from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from git import Repo
from PyQt6.QtCore import Qt

from gitbroom.core.models import AppSettings, BranchInfo, MergeType, RiskLevel, RiskScore
from gitbroom.ui.widgets.delete_dialog import DeleteDialog


def _make_branch(
    name: str = "feature/test",
    is_local: bool = True,
    is_remote: bool = False,
) -> BranchInfo:
    return BranchInfo(
        name=name,
        is_local=is_local,
        is_remote=is_remote,
        last_commit_sha="a" * 40,
        last_commit_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        last_commit_author="Alice",
        last_commit_message="commit",
        is_merged=True,
        merge_type=MergeType.STANDARD,
        merged_at=None,
        merged_into="main",
        ahead_count=0,
        behind_count=0,
        risk_score=RiskScore(level=RiskLevel.GREEN, label="Güvenli Sil", icon="🟢"),
    )


class TestDeleteDialogInit:
    def test_delete_button_disabled_on_open(self, qtbot):
        branch = _make_branch()
        dialog = DeleteDialog([branch], "/fake/path", AppSettings())
        qtbot.addWidget(dialog)
        assert not dialog._btn_delete.isEnabled()

    def test_local_checkbox_checked_for_local_branch(self, qtbot):
        branch = _make_branch(is_local=True, is_remote=False)
        dialog = DeleteDialog([branch], "/fake/path", AppSettings())
        qtbot.addWidget(dialog)
        assert dialog.delete_local() is True
        assert dialog.delete_remote() is False

    def test_remote_checkbox_checked_for_remote_branch(self, qtbot):
        branch = _make_branch(is_local=False, is_remote=True)
        dialog = DeleteDialog([branch], "/fake/path", AppSettings())
        qtbot.addWidget(dialog)
        assert dialog.delete_remote() is True
        assert dialog.delete_local() is False

    def test_both_checkboxes_for_local_and_remote(self, qtbot):
        branch = _make_branch(is_local=True, is_remote=True)
        dialog = DeleteDialog([branch], "/fake/path", AppSettings())
        qtbot.addWidget(dialog)
        assert dialog.delete_local() is True
        assert dialog.delete_remote() is True

    def test_backup_checkbox_follows_settings(self, qtbot):
        settings = AppSettings(create_backup_tag=False)
        branch = _make_branch()
        dialog = DeleteDialog([branch], "/fake/path", settings)
        qtbot.addWidget(dialog)
        assert dialog.create_backup() is False

    def test_countdown_enables_button(self, qtbot):
        branch = _make_branch()
        dialog = DeleteDialog([branch], "/fake/path", AppSettings())
        qtbot.addWidget(dialog)
        # Simulate countdown finishing
        dialog._countdown = 1
        dialog._tick()
        assert dialog._btn_delete.isEnabled()


class TestDeleteDialogExecution:
    def _make_repo(self, tmp_path: Path) -> tuple[Repo, str]:
        repo = Repo.init(tmp_path / "repo")
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=str(tmp_path / "repo"), check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=str(tmp_path / "repo"), check=True, capture_output=True
        )
        (tmp_path / "repo" / "f.txt").write_text("x")
        repo.index.add(["f.txt"])
        repo.index.commit("init")
        if repo.heads:
            repo.heads[0].rename("main")
        repo.create_head("feature/to-delete")
        return repo, str(tmp_path / "repo")

    def test_deletes_local_branch_on_confirm(self, qtbot, tmp_path, monkeypatch):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        repo, repo_path = self._make_repo(tmp_path)

        branch = _make_branch("feature/to-delete", is_local=True, is_remote=False)
        dialog = DeleteDialog([branch], repo_path, AppSettings(create_backup_tag=False))
        qtbot.addWidget(dialog)

        # Force-enable the button (skip countdown in test)
        dialog._btn_delete.setEnabled(True)
        dialog._chk_local.setChecked(True)
        dialog._chk_remote.setChecked(False)

        qtbot.mouseClick(dialog._btn_delete, Qt.MouseButton.LeftButton)

        remaining = [h.name for h in repo.heads]
        assert "feature/to-delete" not in remaining
