from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from git import Repo

from gitbroom.ui.widgets.commit_detail_dialog import CommitDetailDialog
from gitbroom.ui.widgets.diff_highlighter import DiffHighlighter


@pytest.fixture()
def git_repo(tmp_path: Path):
    """Minimal repo with two commits so we have a diff to inspect."""
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()

    (tmp_path / "hello.py").write_text("print('hello')\n")
    repo.index.add(["hello.py"])
    first = repo.index.commit("initial commit")

    (tmp_path / "hello.py").write_text("print('hello world')\n")
    repo.index.add(["hello.py"])
    second = repo.index.commit("update hello")

    branch_name = repo.active_branch.name   # "master" or "main" depending on git config
    return repo, str(tmp_path), first.hexsha, second.hexsha, branch_name


def _make_dialog(qtbot, repo_path: str, sha: str, msg: str = "update hello") -> CommitDetailDialog:
    """Create CommitDetailDialog with diff loading suppressed."""
    with patch.object(CommitDetailDialog, "_load_diff"):
        dlg = CommitDetailDialog(
            repo_path=repo_path,
            commit_sha=sha,
            short_sha=sha[:7],
            commit_message=msg,
            author="Test User",
        )
    qtbot.addWidget(dlg)
    return dlg


class TestCommitDetailDialogInit:
    def test_window_title_contains_short_sha(self, qtbot, git_repo):
        _repo, repo_path, _first_sha, second_sha, _branch = git_repo
        dlg = _make_dialog(qtbot, repo_path, second_sha)
        assert second_sha[:7] in dlg.windowTitle()
        assert "update hello" in dlg.windowTitle()

    def test_dialog_is_resizable(self, qtbot, git_repo):
        _repo, repo_path, _first_sha, second_sha, _branch = git_repo
        dlg = _make_dialog(qtbot, repo_path, second_sha)
        assert dlg.width() >= 800
        assert dlg.height() >= 500


class TestCommitDiffLoader:
    def test_loads_changed_files(self, qapp, git_repo, qtbot):
        _repo, repo_path, _first_sha, second_sha, _branch = git_repo
        from gitbroom.ui.workers import CommitDiffLoader

        loader = CommitDiffLoader(repo_path, second_sha)
        results = []
        loader.diff_loaded.connect(results.append)
        with qtbot.waitSignal(loader.diff_loaded, timeout=5000):
            loader.start()

        assert len(results) == 1
        files = results[0]
        assert len(files) == 1
        assert files[0]["path"] == "hello.py"
        assert files[0]["change_type"] == "M"
        assert files[0]["additions"] >= 1
        assert files[0]["deletions"] >= 1

    def test_diff_text_contains_expected_content(self, qapp, git_repo, qtbot):
        _repo, repo_path, _first_sha, second_sha, _branch = git_repo
        from gitbroom.ui.workers import CommitDiffLoader

        loader = CommitDiffLoader(repo_path, second_sha)
        results = []
        loader.diff_loaded.connect(results.append)
        with qtbot.waitSignal(loader.diff_loaded, timeout=5000):
            loader.start()

        diff_text = results[0][0]["diff_text"]
        assert "+print('hello world')" in diff_text
        assert "-print('hello')" in diff_text

    def test_first_commit_no_parent(self, qapp, git_repo, qtbot):
        _repo, repo_path, first_sha, _second_sha, _branch = git_repo
        from gitbroom.ui.workers import CommitDiffLoader

        loader = CommitDiffLoader(repo_path, first_sha)
        results = []
        loader.diff_loaded.connect(results.append)
        with qtbot.waitSignal(loader.diff_loaded, timeout=5000):
            loader.start()

        files = results[0]
        assert len(files) == 1
        assert files[0]["path"] == "hello.py"
        assert files[0]["change_type"] == "A"


class TestCommitLoader:
    def test_loads_commits(self, qapp, git_repo, qtbot):
        _repo, repo_path, _first_sha, _second_sha, branch_name = git_repo
        from gitbroom.ui.workers import CommitLoader

        loader = CommitLoader(repo_path, branch_name, max_count=5)
        results = []
        loader.commits_loaded.connect(results.append)
        with qtbot.waitSignal(loader.commits_loaded, timeout=5000):
            loader.start()

        commits = results[0]
        assert len(commits) == 2
        assert commits[0]["message"] == "update hello"
        assert len(commits[0]["short_sha"]) == 7
        assert commits[0]["author"] == "Test User"

    def test_max_count_respected(self, qapp, git_repo, qtbot):
        _repo, repo_path, _first_sha, _second_sha, branch_name = git_repo
        from gitbroom.ui.workers import CommitLoader

        loader = CommitLoader(repo_path, branch_name, max_count=1)
        results = []
        loader.commits_loaded.connect(results.append)
        with qtbot.waitSignal(loader.commits_loaded, timeout=5000):
            loader.start()

        assert len(results[0]) == 1


class TestDiffHighlighter:
    def test_instantiates_on_document(self, qapp):
        from PyQt6.QtGui import QTextDocument
        doc = QTextDocument()
        highlighter = DiffHighlighter(doc)
        assert highlighter is not None
