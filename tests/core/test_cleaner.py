from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from git import Repo

from gitbroom.core.cleaner import SafeDeleter


def _configure_repo(path: Path) -> None:
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True, capture_output=True)


@pytest.fixture
def repo_with_feature(tmp_path):
    repo = Repo.init(tmp_path / "repo")
    _configure_repo(tmp_path / "repo")
    (tmp_path / "repo" / "file.txt").write_text("hello")
    repo.index.add(["file.txt"])
    repo.index.commit("initial commit")
    if repo.heads:
        repo.heads[0].rename("main")
    repo.create_head("feature/delete-me")
    return repo


@pytest.fixture
def deleter() -> SafeDeleter:
    return SafeDeleter()


class TestSafetyCheck:
    def test_cannot_delete_active_branch(self, deleter, repo_with_feature):
        # HEAD is on 'main'
        with pytest.raises(ValueError, match="active branch"):
            deleter._safety_check("main", repo_with_feature)

    def test_can_delete_non_active_branch(self, deleter, repo_with_feature):
        # Should not raise
        deleter._safety_check("feature/delete-me", repo_with_feature)


class TestDeleteLocal:
    def test_deletes_local_branch(self, deleter, repo_with_feature, tmp_path, monkeypatch):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        results = deleter.delete_branches(
            ["feature/delete-me"],
            repo_with_feature,
            delete_local=True,
            delete_remote=False,
            create_backup=False,
        )
        assert len(results) == 1
        assert results[0].local_deleted is True
        assert results[0].errors == []
        remaining = [h.name for h in repo_with_feature.heads]
        assert "feature/delete-me" not in remaining

    def test_does_not_delete_active_branch(self, deleter, repo_with_feature, tmp_path, monkeypatch):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        with pytest.raises(ValueError, match="active branch"):
            deleter.delete_branches(
                ["main"],
                repo_with_feature,
                delete_local=True,
                delete_remote=False,
                create_backup=False,
            )

    def test_delete_nonexistent_local_branch_no_error(self, deleter, repo_with_feature, tmp_path, monkeypatch):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        results = deleter.delete_branches(
            ["nonexistent"],
            repo_with_feature,
            delete_local=True,
            delete_remote=False,
            create_backup=False,
        )
        assert results[0].errors == []
        assert results[0].local_deleted is False


class TestBackupTag:
    def test_creates_backup_tag(self, deleter, repo_with_feature, tmp_path, monkeypatch):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        results = deleter.delete_branches(
            ["feature/delete-me"],
            repo_with_feature,
            delete_local=True,
            delete_remote=False,
            create_backup=True,
        )
        assert results[0].backup_tag is not None
        assert results[0].backup_tag.startswith("backup/feature-delete-me-")
        tag_names = [t.name for t in repo_with_feature.tags]
        assert results[0].backup_tag in tag_names

    def test_no_backup_tag_when_disabled(self, deleter, repo_with_feature, tmp_path, monkeypatch):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        results = deleter.delete_branches(
            ["feature/delete-me"],
            repo_with_feature,
            delete_local=True,
            delete_remote=False,
            create_backup=False,
        )
        assert results[0].backup_tag is None


class TestDeletionLog:
    def test_writes_deletion_log(self, deleter, repo_with_feature, tmp_path, monkeypatch):
        import json
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        deleter.delete_branches(
            ["feature/delete-me"],
            repo_with_feature,
            delete_local=True,
            delete_remote=False,
            create_backup=False,
        )
        log_path = tmp_path / "deletion.log"
        assert log_path.exists()
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["branch"] == "feature/delete-me"
        assert entry["delete_local"] is True


class TestMultipleBranches:
    def test_deletes_multiple_branches(self, deleter, tmp_path, monkeypatch):
        monkeypatch.setenv("GITBROOM_CONFIG_DIR", str(tmp_path))
        repo = Repo.init(tmp_path / "repo")
        _configure_repo(tmp_path / "repo")
        (tmp_path / "repo" / "file.txt").write_text("hello")
        repo.index.add(["file.txt"])
        repo.index.commit("initial")
        if repo.heads:
            repo.heads[0].rename("main")
        repo.create_head("feature/a")
        repo.create_head("feature/b")

        results = deleter.delete_branches(
            ["feature/a", "feature/b"],
            repo,
            delete_local=True,
            delete_remote=False,
            create_backup=False,
        )
        assert len(results) == 2
        assert all(r.local_deleted for r in results)
        assert all(r.errors == [] for r in results)
