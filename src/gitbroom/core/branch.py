from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from git import Repo

from gitbroom.core.models import BranchInfo, MergeType, RiskLevel, RiskScore


class BranchCollector:
    def get_branches(self, repo: Repo, default_branch: str) -> list[dict]:
        """Collect local and remote branches, excluding HEAD and default branch."""
        branches: dict[str, dict] = {}

        for ref in repo.heads:
            if ref.name == default_branch:
                continue
            branches[ref.name] = {
                "name": ref.name,
                "is_local": True,
                "is_remote": False,
                "commit": ref.commit,
                "tracking_remote": ref.tracking_branch().name if ref.tracking_branch() else None,
            }

        for remote in repo.remotes:
            for ref in remote.refs:
                parts = ref.name.split("/", 1)
                if len(parts) < 2:
                    continue
                name = parts[1]
                if name in ("HEAD", default_branch):
                    continue
                if name in branches:
                    branches[name]["is_remote"] = True
                else:
                    branches[name] = {
                        "name": name,
                        "is_local": False,
                        "is_remote": True,
                        "commit": ref.commit,
                        "tracking_remote": ref.name,
                    }

        return list(branches.values())


_PLACEHOLDER_RISK = RiskScore(
    level=RiskLevel.ORANGE,
    label="Bekle",
    icon="🟠",
    reasons=[],
)


class BranchAnalyzer:
    """
    Analyze branches for merge status, ahead/behind counts, etc.

    Call prepare() once before analyzing many branches — it pre-computes
    expensive data (merged set, default-branch trees) so per-branch work
    is O(1) lookups instead of repeated git traversals.
    """

    def __init__(self) -> None:
        self._merged_names: set[str] = set()
        self._default_trees: set[str] = set()
        self._default_commit: Any = None
        self._default_name: str = ""
        self._enable_rebase: bool = False
        self._prepared: bool = False

    # ── Public API ───────────────────────────────────────────────────────────

    def prepare(self, repo: Repo, default_branch_ref: Any, enable_rebase: bool = False) -> None:
        """
        Pre-compute per-repo data. Call once before the per-branch loop.

        P1: Batch merged-branch detection via `git branch --merged` (one CLI
            call instead of one merge_base() per branch).
        P2: Build a set of default-branch commit trees for O(1) squash
            detection instead of iterating 200 commits per branch.
        """
        self._enable_rebase = enable_rebase
        self._default_commit = default_branch_ref.commit
        self._default_name = default_branch_ref.name

        # P1 — batch standard-merge detection
        self._merged_names = self._fetch_merged_names(repo, default_branch_ref.name)

        # P2 — pre-compute squash detection set (tree SHAs)
        try:
            self._default_trees = {
                c.tree.hexsha
                for c in default_branch_ref.commit.iter_items(
                    repo, default_branch_ref, max_count=100
                )
            }
        except Exception:
            self._default_trees = set()

        self._prepared = True

    def analyze(self, branch_dict: dict, repo: Repo, default_branch_ref: Any) -> BranchInfo:
        """Analyze a single branch. Call prepare() first for best performance."""
        if not self._prepared:
            self.prepare(repo, default_branch_ref)

        commit = branch_dict["commit"]
        commit_date = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)

        is_merged, merge_type = self._get_merge_status(branch_dict["name"], commit, repo)

        # P4 — ahead/behind via fast git rev-list (no merge_base needed)
        ahead, behind = self._get_ahead_behind(commit, repo)

        return BranchInfo(
            name=branch_dict["name"],
            is_local=branch_dict["is_local"],
            is_remote=branch_dict["is_remote"],
            last_commit_sha=commit.hexsha,
            last_commit_date=commit_date,
            last_commit_author=commit.author.name or commit.author.email or "Unknown",
            last_commit_message=commit.message.strip().splitlines()[0],
            is_merged=is_merged,
            merge_type=merge_type,
            merged_at=None,
            merged_into=self._default_name if is_merged else None,
            ahead_count=ahead,
            behind_count=behind,
            risk_score=_PLACEHOLDER_RISK,
        )

    # ── Merge detection ──────────────────────────────────────────────────────

    def _get_merge_status(
        self, branch_name: str, commit: Any, repo: Repo
    ) -> tuple[bool, MergeType]:
        # P1 — O(1) set lookup (pre-computed)
        if branch_name in self._merged_names:
            return True, MergeType.STANDARD

        # P2 — O(1) tree-SHA lookup (pre-computed)
        if commit.tree.hexsha in self._default_trees:
            return True, MergeType.SQUASH

        # P3 — rebase detection is opt-in (disabled by default, expensive)
        if self._enable_rebase and self._detect_rebase_merge(commit, repo):
            return True, MergeType.REBASE

        return False, MergeType.NOT_MERGED

    def _detect_rebase_merge(self, branch_commit: Any, repo: Repo) -> bool:
        """Opt-in. Compares patch-ids; only enabled when AppSettings.enable_rebase_detection=True."""
        try:
            branch_patches = {
                self._patch_id(c)
                for c in branch_commit.iter_items(repo, branch_commit, max_count=20)
                if c.parents
            }
            if not branch_patches:
                return False

            default_patches = {
                self._patch_id(c)
                for c in self._default_commit.iter_items(repo, self._default_commit, max_count=100)
                if c.parents
            }
            return branch_patches.issubset(default_patches)
        except Exception:
            return False

    def _patch_id(self, commit: Any) -> str:
        if not commit.parents:
            return commit.hexsha
        import hashlib
        diff = commit.parents[0].diff(commit, create_patch=True)
        content = "".join(d.diff.decode("utf-8", errors="replace") for d in diff)
        return hashlib.sha1(content.encode()).hexdigest()

    # ── Ahead / behind ───────────────────────────────────────────────────────

    def _get_ahead_behind(self, branch_commit: Any, repo: Repo) -> tuple[int, int]:
        """
        P4 — use `git rev-list --count` (native C, no Python iteration).
        No merge_base() call required.
        """
        try:
            default_sha = self._default_commit.hexsha
            branch_sha = branch_commit.hexsha
            ahead = int(repo.git.rev_list("--count", f"{default_sha}..{branch_sha}"))
            behind = int(repo.git.rev_list("--count", f"{branch_sha}..{default_sha}"))
            return ahead, behind
        except Exception:
            return 0, 0

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _fetch_merged_names(repo: Repo, default_ref_name: str) -> set[str]:
        """Run git branch --merged once to get all merged branch names."""
        merged: set[str] = set()
        try:
            out = repo.git.branch("--merged", default_ref_name)
            for line in out.splitlines():
                name = line.strip().lstrip("* ")
                if name:
                    merged.add(name)
        except Exception:
            pass
        try:
            # Remote branches merged into default
            out = repo.git.branch("-r", "--merged", default_ref_name)
            for line in out.splitlines():
                name = line.strip()
                if "/" in name:
                    name = name.split("/", 1)[1]  # strip "origin/" prefix
                    if name not in ("HEAD",):
                        merged.add(name)
        except Exception:
            pass
        return merged
