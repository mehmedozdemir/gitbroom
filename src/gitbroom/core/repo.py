from __future__ import annotations

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import GitCommandError


class RepoManager:
    def load(self, path: str) -> Repo:
        """Load a git repository from path, searching parent directories."""
        try:
            repo = Repo(path, search_parent_directories=True)
        except InvalidGitRepositoryError:
            raise ValueError(f"'{path}' is not a valid git repository.")
        except NoSuchPathError:
            raise ValueError(f"Path '{path}' does not exist.")

        if repo.bare:
            raise ValueError("Bare repositories are not supported.")

        return repo

    def validate(self, repo: Repo) -> list[str]:
        """Return a list of warnings about the repository state."""
        warnings: list[str] = []

        if not repo.remotes:
            warnings.append("No remotes configured — remote operations will be unavailable.")

        try:
            repo.active_branch
        except TypeError:
            warnings.append("Repository is in detached HEAD state.")

        return warnings

    def get_default_branch(self, repo: Repo) -> str:
        """Detect the default branch name."""
        # 1. Try origin/HEAD symbolic reference
        for remote in repo.remotes:
            if remote.name == "origin":
                try:
                    ref = remote.refs["HEAD"]
                    target = ref.reference.name  # e.g. "origin/main"
                    return target.split("/", 1)[1]
                except (IndexError, AttributeError, KeyError):
                    pass

        # 2. Check common names in repo heads
        local_names = {h.name for h in repo.heads}
        for candidate in ("main", "master", "develop"):
            if candidate in local_names:
                return candidate

        # 3. Fall back to the first local branch
        if repo.heads:
            return repo.heads[0].name

        return "main"

    def get_remotes(self, repo: Repo) -> list[str]:
        """Return names of all configured remotes."""
        return [r.name for r in repo.remotes]

    def fetch_remote(self, repo: Repo, remote: str = "origin") -> bool:
        """Fetch from remote. Returns True on success, False on failure."""
        try:
            matching = [r for r in repo.remotes if r.name == remote]
            if not matching:
                return False
            matching[0].fetch()
            return True
        except GitCommandError:
            return False
