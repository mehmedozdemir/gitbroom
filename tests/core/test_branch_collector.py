import pytest
from git import Repo

from gitbroom.core.branch import BranchCollector


def _make_repo_with_branches(tmp_path, branch_names: list[str], default: str = "main") -> Repo:
    repo = Repo.init(tmp_path / "repo")
    (tmp_path / "repo" / "file.txt").write_text("hello")
    repo.index.add(["file.txt"])
    # Create initial commit on default branch
    initial = repo.index.commit("initial commit")

    # Rename initial branch to default if needed
    if repo.heads:
        repo.heads[0].rename(default)

    for name in branch_names:
        repo.create_head(name)

    return repo


@pytest.fixture
def collector() -> BranchCollector:
    return BranchCollector()


class TestGetBranches:
    def test_excludes_default_branch(self, collector, tmp_path):
        repo = _make_repo_with_branches(tmp_path, ["feature/a", "fix/b"], default="main")
        results = collector.get_branches(repo, "main")
        names = [b["name"] for b in results]
        assert "main" not in names

    def test_includes_non_default_branches(self, collector, tmp_path):
        repo = _make_repo_with_branches(tmp_path, ["feature/a", "fix/b"])
        results = collector.get_branches(repo, "main")
        names = [b["name"] for b in results]
        assert "feature/a" in names
        assert "fix/b" in names

    def test_local_branch_flags(self, collector, tmp_path):
        repo = _make_repo_with_branches(tmp_path, ["feature/x"])
        results = collector.get_branches(repo, "main")
        branch = next(b for b in results if b["name"] == "feature/x")
        assert branch["is_local"] is True
        assert branch["is_remote"] is False

    def test_empty_repo_no_branches(self, collector, tmp_path):
        repo = _make_repo_with_branches(tmp_path, [])
        results = collector.get_branches(repo, "main")
        assert results == []

    def test_returns_commit_object(self, collector, tmp_path):
        repo = _make_repo_with_branches(tmp_path, ["feature/y"])
        results = collector.get_branches(repo, "main")
        branch = next(b for b in results if b["name"] == "feature/y")
        assert branch["commit"] is not None

    def test_remote_branch_merged_with_local(self, collector, tmp_path):
        """A branch that exists both locally and as remote should have both flags True."""
        origin_path = tmp_path / "origin"
        local_path = tmp_path / "local"

        # Create origin with a branch
        origin = Repo.init(origin_path)
        (origin_path / "file.txt").write_text("hello")
        origin.index.add(["file.txt"])
        origin.index.commit("init")
        if origin.heads:
            origin.heads[0].rename("main")
        origin.create_head("feature/shared")

        # Clone it
        cloned = Repo.clone_from(str(origin_path), str(local_path))
        # Checkout the remote branch locally
        cloned.create_head("feature/shared", cloned.remotes.origin.refs["feature/shared"])

        results = collector.get_branches(cloned, "main")
        branch = next((b for b in results if b["name"] == "feature/shared"), None)
        assert branch is not None
        assert branch["is_local"] is True
        assert branch["is_remote"] is True

    def test_only_remote_branch_not_local(self, collector, tmp_path):
        """A remote-only branch should appear with is_local=False."""
        origin_path = tmp_path / "origin"
        local_path = tmp_path / "local"

        origin = Repo.init(origin_path)
        (origin_path / "file.txt").write_text("hello")
        origin.index.add(["file.txt"])
        origin.index.commit("init")
        if origin.heads:
            origin.heads[0].rename("main")
        origin.create_head("remote-only")

        cloned = Repo.clone_from(str(origin_path), str(local_path))

        results = collector.get_branches(cloned, "main")
        branch = next((b for b in results if b["name"] == "remote-only"), None)
        assert branch is not None
        assert branch["is_local"] is False
        assert branch["is_remote"] is True
