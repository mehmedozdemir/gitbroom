import pytest
from git import Repo

from gitbroom.core.repo import RepoManager


@pytest.fixture
def manager() -> RepoManager:
    return RepoManager()


@pytest.fixture
def bare_repo(tmp_path):
    return Repo.init(tmp_path / "bare.git", bare=True)


@pytest.fixture
def empty_repo(tmp_path):
    return Repo.init(tmp_path / "repo")


@pytest.fixture
def repo_with_commit(tmp_path):
    repo = Repo.init(tmp_path / "repo")
    (tmp_path / "repo" / "file.txt").write_text("hello")
    repo.index.add(["file.txt"])
    repo.index.commit("initial commit")
    return repo


@pytest.fixture
def repo_with_branches(tmp_path):
    repo = Repo.init(tmp_path / "repo")
    (tmp_path / "repo" / "file.txt").write_text("hello")
    repo.index.add(["file.txt"])
    repo.index.commit("initial commit")
    repo.create_head("develop")
    repo.create_head("feature/test")
    return repo


class TestLoad:
    def test_loads_valid_repo(self, manager, repo_with_commit):
        repo = manager.load(str(repo_with_commit.working_dir))
        assert repo is not None
        assert not repo.bare

    def test_raises_on_non_repo_path(self, manager, tmp_path):
        non_repo = tmp_path / "not_a_repo"
        non_repo.mkdir()
        with pytest.raises(ValueError, match="not a valid git repository"):
            manager.load(str(non_repo))

    def test_raises_on_nonexistent_path(self, manager):
        with pytest.raises(ValueError, match="does not exist"):
            manager.load("/nonexistent/path/xyz")

    def test_raises_on_bare_repo(self, manager, tmp_path):
        bare_path = tmp_path / "bare.git"
        Repo.init(str(bare_path), bare=True)
        with pytest.raises(ValueError, match="Bare repositories"):
            manager.load(str(bare_path))

    def test_search_parent_directories(self, manager, repo_with_commit, tmp_path):
        subdir = repo_with_commit.working_dir + "/subdir"
        import os
        os.makedirs(subdir, exist_ok=True)
        repo = manager.load(subdir)
        assert repo is not None


class TestValidate:
    def test_no_warnings_for_clean_repo(self, manager, repo_with_commit):
        warnings = manager.validate(repo_with_commit)
        # No remotes → one warning expected
        assert any("remote" in w.lower() for w in warnings)

    def test_warns_on_no_remotes(self, manager, repo_with_commit):
        warnings = manager.validate(repo_with_commit)
        assert len(warnings) == 1
        assert "remote" in warnings[0].lower()

    def test_no_warnings_on_detached_head(self, manager, repo_with_commit):
        # Detach HEAD
        repo_with_commit.head.reference = repo_with_commit.head.commit
        repo_with_commit.head.reset(index=True, working_tree=False)
        warnings = manager.validate(repo_with_commit)
        assert any("detached" in w.lower() for w in warnings)


class TestGetDefaultBranch:
    def test_finds_main(self, manager, repo_with_commit):
        # Repo was initialized, default head is 'master' or 'main' depending on git config
        default = manager.get_default_branch(repo_with_commit)
        assert default in ("main", "master")

    def test_prefers_main_over_master(self, manager, tmp_path):
        repo = Repo.init(tmp_path / "repo")
        (tmp_path / "repo" / "f.txt").write_text("x")
        repo.index.add(["f.txt"])
        repo.index.commit("init")
        # Rename to master then create main
        try:
            repo.heads[0].rename("master")
            repo.create_head("main")
        except Exception:
            pass
        default = manager.get_default_branch(repo)
        assert default == "main"

    def test_falls_back_to_first_branch(self, manager, tmp_path):
        repo = Repo.init(tmp_path / "repo")
        (tmp_path / "repo" / "f.txt").write_text("x")
        repo.index.add(["f.txt"])
        repo.index.commit("init")
        repo.heads[0].rename("custom-default")
        default = manager.get_default_branch(repo)
        assert default == "custom-default"

    def test_returns_main_when_no_branches(self, manager, empty_repo):
        default = manager.get_default_branch(empty_repo)
        assert default == "main"


class TestGetRemotes:
    def test_returns_empty_for_no_remotes(self, manager, repo_with_commit):
        remotes = manager.get_remotes(repo_with_commit)
        assert remotes == []

    def test_returns_remote_names(self, manager, repo_with_commit, tmp_path):
        origin_path = tmp_path / "origin"
        Repo.clone_from(str(repo_with_commit.working_dir), str(origin_path))
        repo = manager.load(str(origin_path))
        remotes = manager.get_remotes(repo)
        assert "origin" in remotes
