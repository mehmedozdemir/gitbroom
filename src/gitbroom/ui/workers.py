from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from gitbroom.core.branch import BranchAnalyzer, BranchCollector
from gitbroom.core.models import AppSettings, BranchInfo
from gitbroom.core.repo import RepoManager
from gitbroom.core.scorer import RiskScorer


class RepoScanWorker(QThread):
    progress = pyqtSignal(int, int, str)   # current, total, branch_name
    branch_found = pyqtSignal(object)      # BranchInfo
    finished = pyqtSignal(list)            # list[BranchInfo]
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

            analyzer = BranchAnalyzer()
            scorer = RiskScorer(self._settings)

            # Resolve default branch ref
            default_ref = None
            for head in repo.heads:
                if head.name == default_branch:
                    default_ref = head
                    break
            if default_ref is None and repo.remotes:
                for remote in repo.remotes:
                    try:
                        default_ref = remote.refs[default_branch]
                        break
                    except (IndexError, KeyError):
                        pass

            if default_ref is None:
                self.error.emit(f"Default branch '{default_branch}' bulunamadı.")
                return

            total = len(branch_dicts)
            results: list[BranchInfo] = []

            for i, branch_dict in enumerate(branch_dicts):
                if self._cancelled:
                    return
                try:
                    info = analyzer.analyze(branch_dict, repo, default_ref)
                    info.risk_score = scorer.score(info)
                    results.append(info)
                    self.branch_found.emit(info)
                    self.progress.emit(i + 1, total, branch_dict["name"])
                except Exception as e:
                    self.error.emit(f"Branch analiz hatası ({branch_dict['name']}): {e}")

            self.finished.emit(results)

        except Exception as e:
            self.error.emit(str(e))


class DeletionWorker(QThread):
    progress = pyqtSignal(int, int, str)   # current, total, branch_name
    finished = pyqtSignal(list)            # list[DeletionResult]
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
