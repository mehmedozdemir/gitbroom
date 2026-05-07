from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from git import Repo

from gitbroom.core.models import BranchInfo, MergeType, RiskLevel, RiskScore


class BranchCollector:
    def get_branches(self, repo: Repo, default_branch: str) -> list[dict]:
        """Collect local and remote branches, excluding HEAD and default branch."""
        branches: dict[str, dict] = {}

        # Local branches
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

        # Remote branches
        for remote in repo.remotes:
            for ref in remote.refs:
                # Strip "origin/" prefix
                parts = ref.name.split("/", 1)
                if len(parts) < 2:
                    continue
                name = parts[1]
                if name in ("HEAD", default_branch):
                    continue

                if name in branches:
                    # Merge into existing local entry
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
    def analyze(self, branch_dict: dict, repo: Repo, default_branch_ref: Any) -> BranchInfo:
        """Analyze a branch dict returned by BranchCollector and produce BranchInfo."""
        commit = branch_dict["commit"]
        commit_date = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)

        is_merged, merge_type, merged_at = self._get_merge_status(
            branch_dict, repo, default_branch_ref
        )
        ahead, behind = self._get_ahead_behind(commit, repo, default_branch_ref)

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
            merged_at=merged_at,
            merged_into=default_branch_ref.name if is_merged else None,
            ahead_count=ahead,
            behind_count=behind,
            risk_score=_PLACEHOLDER_RISK,  # scorer fills this in later
        )

    def _get_merge_status(
        self, branch_dict: dict, repo: Repo, default_branch_ref: Any
    ) -> tuple[bool, MergeType, datetime | None]:
        commit = branch_dict["commit"]
        default_commit = default_branch_ref.commit

        # 1. Standard merge
        if self._is_standard_merged(commit, default_commit, repo):
            return True, MergeType.STANDARD, self._find_merge_date(commit, repo, default_commit)

        # 2. Squash merge
        if self._detect_squash_merge(commit, repo, default_branch_ref):
            return True, MergeType.SQUASH, None

        # 3. Rebase merge
        if self._detect_rebase_merge(commit, repo, default_branch_ref):
            return True, MergeType.REBASE, None

        return False, MergeType.NOT_MERGED, None

    def _is_standard_merged(self, branch_commit: Any, default_commit: Any, repo: Repo) -> bool:
        try:
            merge_base = repo.merge_base(branch_commit, default_commit)
            return bool(merge_base) and merge_base[0] == branch_commit
        except Exception:
            return False

    def _find_merge_date(
        self, branch_commit: Any, repo: Repo, default_commit: Any
    ) -> datetime | None:
        """Walk default branch to find the merge commit that introduced branch_commit."""
        try:
            for commit in default_commit.iter_items(repo, default_commit, max_count=500):
                if len(commit.parents) > 1:
                    for parent in commit.parents:
                        if parent == branch_commit:
                            return datetime.fromtimestamp(
                                commit.committed_date, tz=timezone.utc
                            )
        except Exception:
            pass
        return None

    def _detect_squash_merge(
        self, branch_commit: Any, repo: Repo, default_branch_ref: Any
    ) -> bool:
        """
        Squash merge leaves the combined tree state on default branch.
        Compare branch tip tree against recent default branch commit trees.
        Max 200 commits for performance.
        """
        try:
            branch_tree = branch_commit.tree
            for commit in default_branch_ref.commit.iter_items(
                repo, default_branch_ref, max_count=200
            ):
                if commit.tree == branch_tree:
                    return True
            return False
        except Exception:
            return False

    def _detect_rebase_merge(
        self, branch_commit: Any, repo: Repo, default_branch_ref: Any
    ) -> bool:
        """
        Rebase merge re-applies patches. Compare patch-ids of branch commits
        against recent default branch commits. Max 50 branch commits checked.
        """
        try:
            branch_patches = set(
                self._patch_id(c)
                for c in branch_commit.iter_items(repo, branch_commit, max_count=50)
                if c.parents  # skip root commits
            )
            if not branch_patches:
                return False

            default_patches = set(
                self._patch_id(c)
                for c in default_branch_ref.commit.iter_items(
                    repo, default_branch_ref, max_count=200
                )
                if c.parents
            )
            # If all branch patches appear in default, it's a rebase merge
            return bool(branch_patches) and branch_patches.issubset(default_patches)
        except Exception:
            return False

    def _patch_id(self, commit: Any) -> str:
        """Stable identifier based on diff content (author-independent)."""
        if not commit.parents:
            return commit.hexsha
        diff = commit.parents[0].diff(commit, create_patch=True)
        content = "".join(d.diff.decode("utf-8", errors="replace") for d in diff)
        import hashlib
        return hashlib.sha1(content.encode()).hexdigest()

    def _get_ahead_behind(
        self, branch_commit: Any, repo: Repo, default_branch_ref: Any
    ) -> tuple[int, int]:
        try:
            default_commit = default_branch_ref.commit
            merge_base = repo.merge_base(branch_commit, default_commit)
            if not merge_base:
                return 0, 0
            base = merge_base[0]

            ahead = sum(
                1 for _ in branch_commit.iter_items(repo, f"{base}..{branch_commit}")
            )
            behind = sum(
                1 for _ in default_commit.iter_items(repo, f"{base}..{default_commit}")
            )
            return ahead, behind
        except Exception:
            return 0, 0
