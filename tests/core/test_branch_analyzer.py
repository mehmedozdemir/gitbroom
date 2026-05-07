from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from git import Actor, Repo

from gitbroom.core.branch import BranchAnalyzer
from gitbroom.core.models import MergeType


def _git(repo_path: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )


def _configure_repo(repo_path: Path) -> None:
    _git(repo_path, "config", "user.email", "test@test.com")
    _git(repo_path, "config", "user.name", "Test User")


def _make_base_repo(tmp_path: Path) -> tuple[Repo, Path]:
    path = tmp_path / "repo"
    Repo.init(str(path))
    _configure_repo(path)

    (path / "base.txt").write_text("base content")
    _git(path, "add", "base.txt")
    _git(path, "commit", "-m", "base commit")
    _git(path, "branch", "-m", "main")

    repo = Repo(str(path))
    return repo, path


@pytest.fixture
def analyzer() -> BranchAnalyzer:
    return BranchAnalyzer()


class TestStandardMerge:
    def test_detects_standard_merge(self, analyzer, tmp_path):
        repo, path = _make_base_repo(tmp_path)

        # Create feature branch
        _git(path, "checkout", "-b", "feature/standard")
        (path / "feature.txt").write_text("feature")
        _git(path, "add", "feature.txt")
        _git(path, "commit", "-m", "feature commit")

        # Merge into main
        _git(path, "checkout", "main")
        _git(path, "merge", "--no-ff", "feature/standard", "-m", "Merge feature/standard")

        repo = Repo(str(path))
        default_ref = repo.heads["main"]
        feature_commit = repo.heads["feature/standard"].commit

        branch_dict = {
            "name": "feature/standard",
            "is_local": True,
            "is_remote": False,
            "commit": feature_commit,
        }

        info = analyzer.analyze(branch_dict, repo, default_ref)
        assert info.is_merged is True
        assert info.merge_type == MergeType.STANDARD

    def test_unmerged_branch_is_not_merged(self, analyzer, tmp_path):
        repo, path = _make_base_repo(tmp_path)

        _git(path, "checkout", "-b", "feature/unmerged")
        (path / "new.txt").write_text("new")
        _git(path, "add", "new.txt")
        _git(path, "commit", "-m", "unmerged commit")

        repo = Repo(str(path))
        default_ref = repo.heads["main"]
        feature_commit = repo.heads["feature/unmerged"].commit

        branch_dict = {
            "name": "feature/unmerged",
            "is_local": True,
            "is_remote": False,
            "commit": feature_commit,
        }

        info = analyzer.analyze(branch_dict, repo, default_ref)
        assert info.is_merged is False
        assert info.merge_type == MergeType.NOT_MERGED
        assert info.merged_into is None


class TestSquashMerge:
    def test_detects_squash_merge(self, analyzer, tmp_path):
        repo, path = _make_base_repo(tmp_path)

        _git(path, "checkout", "-b", "feature/squash")
        (path / "squash.txt").write_text("squash content")
        _git(path, "add", "squash.txt")
        _git(path, "commit", "-m", "squash commit 1")
        (path / "squash.txt").write_text("squash content v2")
        _git(path, "add", "squash.txt")
        _git(path, "commit", "-m", "squash commit 2")

        feature_commit = Repo(str(path)).heads["feature/squash"].commit

        _git(path, "checkout", "main")
        _git(path, "merge", "--squash", "feature/squash")
        _git(path, "commit", "-m", "Squash merge feature/squash")

        repo = Repo(str(path))
        default_ref = repo.heads["main"]

        branch_dict = {
            "name": "feature/squash",
            "is_local": True,
            "is_remote": False,
            "commit": feature_commit,
        }

        info = analyzer.analyze(branch_dict, repo, default_ref)
        # Squash merge: the tree of main after squash == tree of feature tip
        assert info.is_merged is True
        assert info.merge_type in (MergeType.SQUASH, MergeType.STANDARD)


class TestBranchInfoFields:
    def test_commit_metadata(self, analyzer, tmp_path):
        repo, path = _make_base_repo(tmp_path)

        _git(path, "checkout", "-b", "feature/meta")
        (path / "meta.txt").write_text("meta")
        _git(path, "add", "meta.txt")
        _git(path, "commit", "-m", "meta commit message")

        repo = Repo(str(path))
        default_ref = repo.heads["main"]
        feature_commit = repo.heads["feature/meta"].commit

        branch_dict = {
            "name": "feature/meta",
            "is_local": True,
            "is_remote": False,
            "commit": feature_commit,
        }

        info = analyzer.analyze(branch_dict, repo, default_ref)
        assert info.name == "feature/meta"
        assert info.last_commit_message == "meta commit message"
        assert info.last_commit_author == "Test User"
        assert len(info.last_commit_sha) == 40
        assert info.last_commit_date is not None

    def test_ahead_behind_counts(self, analyzer, tmp_path):
        repo, path = _make_base_repo(tmp_path)

        _git(path, "checkout", "-b", "feature/counts")
        (path / "f1.txt").write_text("f1")
        _git(path, "add", "f1.txt")
        _git(path, "commit", "-m", "feature commit 1")
        (path / "f2.txt").write_text("f2")
        _git(path, "add", "f2.txt")
        _git(path, "commit", "-m", "feature commit 2")

        repo = Repo(str(path))
        default_ref = repo.heads["main"]
        feature_commit = repo.heads["feature/counts"].commit

        branch_dict = {
            "name": "feature/counts",
            "is_local": True,
            "is_remote": False,
            "commit": feature_commit,
        }

        info = analyzer.analyze(branch_dict, repo, default_ref)
        assert info.ahead_count == 2
        assert info.behind_count == 0

    def test_behind_count_when_main_has_new_commits(self, analyzer, tmp_path):
        repo, path = _make_base_repo(tmp_path)

        _git(path, "checkout", "-b", "feature/behind")
        (path / "feat.txt").write_text("feat")
        _git(path, "add", "feat.txt")
        _git(path, "commit", "-m", "feat commit")
        feature_commit_sha = Repo(str(path)).heads["feature/behind"].commit

        # Add commits to main after branch point
        _git(path, "checkout", "main")
        (path / "main_extra.txt").write_text("extra")
        _git(path, "add", "main_extra.txt")
        _git(path, "commit", "-m", "main extra commit")

        repo = Repo(str(path))
        default_ref = repo.heads["main"]
        feature_commit = repo.heads["feature/behind"].commit

        branch_dict = {
            "name": "feature/behind",
            "is_local": True,
            "is_remote": False,
            "commit": feature_commit,
        }

        info = analyzer.analyze(branch_dict, repo, default_ref)
        assert info.ahead_count == 1
        assert info.behind_count == 1
