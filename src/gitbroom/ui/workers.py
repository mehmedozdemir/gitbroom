from __future__ import annotations

import logging
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal

from gitbroom.core.branch import BranchAnalyzer, BranchCollector
from gitbroom.core.models import AppSettings, BranchInfo
from gitbroom.core.repo import RepoManager
from gitbroom.core.scorer import RiskScorer

logger = logging.getLogger(__name__)


class RepoScanWorker(QThread):
    progress = pyqtSignal(int, int, str)   # current, total, branch_name
    branch_found = pyqtSignal(object)      # BranchInfo — emitted per branch for streaming
    finished = pyqtSignal(list)            # list[BranchInfo] — full result at end
    error = pyqtSignal(str)

    def __init__(self, repo_path: str, settings: AppSettings) -> None:
        super().__init__()
        self._repo_path = repo_path
        self._settings = settings
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            manager = RepoManager()
            repo = manager.load(self._repo_path)
            default_branch = manager.get_default_branch(repo)

            collector = BranchCollector()
            branch_dicts = collector.get_branches(repo, default_branch)

            scorer = RiskScorer(self._settings)
            analyzer = BranchAnalyzer()

            # Resolve default branch ref (local head preferred, remote fallback)
            default_ref = None
            for head in repo.heads:
                if head.name == default_branch:
                    default_ref = head
                    break
            if default_ref is None:
                for remote in repo.remotes:
                    try:
                        default_ref = remote.refs[default_branch]
                        break
                    except (IndexError, KeyError):
                        pass

            if default_ref is None:
                self.error.emit(f"Default branch '{default_branch}' bulunamadı.")
                return

            # P1+P2: Pre-compute merged set + default trees ONCE (not per branch)
            analyzer.prepare(
                repo,
                default_ref,
                enable_rebase=self._settings.enable_rebase_detection,
            )

            total = len(branch_dicts)
            results: list[BranchInfo] = []

            for i, branch_dict in enumerate(branch_dicts):
                if self._cancelled:
                    return
                try:
                    info = analyzer.analyze(branch_dict, repo, default_ref)
                    info.risk_score = scorer.score(info)
                    results.append(info)
                    self.branch_found.emit(info)      # P6: stream to UI immediately
                    self.progress.emit(i + 1, total, branch_dict["name"])
                except Exception as e:
                    logger.warning("Branch analiz hatası (%s): %s", branch_dict["name"], e)
                    self.error.emit(f"Analiz atlandı ({branch_dict['name']}): {e}")

            self.finished.emit(results)

        except Exception as e:
            logger.error("Scan failed: %s", e)
            self.error.emit(str(e))


class CommitLoader(QThread):
    commits_loaded = pyqtSignal(list)   # list[dict]
    error = pyqtSignal(str)

    def __init__(self, repo_path: str, branch_name: str, max_count: int = 5, is_local: bool = True) -> None:
        super().__init__()
        self._repo_path = repo_path
        self._branch_name = branch_name
        self._max_count = max_count
        self._is_local = is_local

    def _resolve_ref(self, repo) -> str:
        """Return the git ref string that points to this branch."""
        if self._is_local:
            return self._branch_name
        # Remote-only: try origin/ prefix; if repo has a different remote, fall back
        for remote in repo.remotes:
            candidate = f"{remote.name}/{self._branch_name}"
            try:
                repo.commit(candidate)
                return candidate
            except Exception:
                continue
        return self._branch_name  # last resort — will likely fail with a useful error

    def run(self) -> None:
        try:
            repo = RepoManager().load(self._repo_path)
            ref = self._resolve_ref(repo)
            commits = []
            for commit in repo.iter_commits(ref, max_count=self._max_count):
                commits.append({
                    "sha": commit.hexsha,
                    "short_sha": commit.hexsha[:7],
                    "message": commit.message.split("\n")[0][:72],
                    "author": commit.author.name,
                    "date": datetime.fromtimestamp(commit.committed_date),
                    "parent_sha": commit.parents[0].hexsha if commit.parents else None,
                })
            self.commits_loaded.emit(commits)
        except Exception as e:
            logger.error("CommitLoader failed: %s", e)
            self.error.emit(str(e))


class CommitDiffLoader(QThread):
    diff_loaded = pyqtSignal(list)   # list[dict]
    error = pyqtSignal(str)

    def __init__(self, repo_path: str, commit_sha: str) -> None:
        super().__init__()
        self._repo_path = repo_path
        self._commit_sha = commit_sha

    def run(self) -> None:
        try:
            repo = RepoManager().load(self._repo_path)
            commit = repo.commit(self._commit_sha)

            if commit.parents:
                # Forward diff: parent → commit (shows what this commit changed)
                diffs = commit.parents[0].diff(commit, create_patch=True)
                first_commit = False
            else:
                # First commit: diff against empty tree (files appear as deleted;
                # we flip change_type to 'A' below for correct display)
                from git import NULL_TREE
                diffs = commit.diff(NULL_TREE, create_patch=True)
                first_commit = True

            files = []
            for d in diffs:
                path = d.b_path or d.a_path or ""
                raw = d.diff if d.diff else b""
                try:
                    diff_text = raw.decode("utf-8", errors="replace")
                except Exception:
                    diff_text = "(binary file)"

                lines = diff_text.splitlines()
                additions = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
                deletions = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))

                if first_commit:
                    change_type = "A"
                elif d.new_file:
                    change_type = "A"
                elif d.deleted_file:
                    change_type = "D"
                elif d.renamed_file:
                    change_type = "R"
                else:
                    change_type = d.change_type or "M"

                files.append({
                    "path": path,
                    "change_type": change_type,
                    "diff_text": diff_text,
                    "additions": additions,
                    "deletions": deletions,
                })
            self.diff_loaded.emit(files)
        except Exception as e:
            logger.error("CommitDiffLoader failed: %s", e)
            self.error.emit(str(e))


class DeletionWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(
        self,
        branches: list[str],
        repo_path: str,
        delete_local: bool,
        delete_remote: bool,
        create_backup: bool,
    ) -> None:
        super().__init__()
        self._branches = branches
        self._repo_path = repo_path
        self._delete_local = delete_local
        self._delete_remote = delete_remote
        self._create_backup = create_backup

    def run(self) -> None:
        try:
            from gitbroom.core.cleaner import SafeDeleter
            manager = RepoManager()
            repo = manager.load(self._repo_path)
            deleter = SafeDeleter()
            results = []
            total = len(self._branches)

            for i, name in enumerate(self._branches):
                self.progress.emit(i + 1, total, name)
                result = deleter.delete_branches(
                    [name], repo,
                    delete_local=self._delete_local,
                    delete_remote=self._delete_remote,
                    create_backup=self._create_backup,
                )
                results.extend(result)

            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))
