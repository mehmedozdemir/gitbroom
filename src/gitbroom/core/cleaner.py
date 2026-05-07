from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from git import GitCommandError, Repo

from gitbroom.core.models import DeletionResult

logger = logging.getLogger(__name__)

_LOG_PATH = Path.home() / ".gitbroom" / "deletion.log"


def _log_path() -> Path:
    env_dir = os.environ.get("GITBROOM_CONFIG_DIR")
    if env_dir:
        return Path(env_dir) / "deletion.log"
    return _LOG_PATH


class SafeDeleter:
    def delete_branches(
        self,
        branches: list[str],
        repo: Repo,
        delete_local: bool,
        delete_remote: bool,
        create_backup: bool,
        remote_name: str = "origin",
    ) -> list[DeletionResult]:
        results: list[DeletionResult] = []
        for name in branches:
            result = self._delete_one(
                name, repo, delete_local, delete_remote, create_backup, remote_name
            )
            results.append(result)
        return results

    def _delete_one(
        self,
        branch_name: str,
        repo: Repo,
        delete_local: bool,
        delete_remote: bool,
        create_backup: bool,
        remote_name: str,
    ) -> DeletionResult:
        self._safety_check(branch_name, repo)

        backup_tag: str | None = None
        if create_backup:
            try:
                backup_tag = self._create_backup_tag(branch_name, repo)
            except Exception as e:
                logger.warning("Backup tag creation failed for %s: %s", branch_name, e)

        errors: list[str] = []
        local_deleted = False
        remote_deleted = False

        if delete_local:
            local_heads = [h for h in repo.heads if h.name == branch_name]
            if local_heads:
                try:
                    repo.delete_head(branch_name, force=False)
                    local_deleted = True
                except GitCommandError as e:
                    errors.append(f"Local silme hatası: {e}")
            else:
                local_deleted = False  # branch doesn't exist locally — not an error

        if delete_remote:
            remote_refs = [r for r in repo.remotes if r.name == remote_name]
            if remote_refs:
                try:
                    remote_refs[0].push(f":refs/heads/{branch_name}")
                    remote_deleted = True
                except GitCommandError as e:
                    errors.append(f"Remote silme hatası: {e}")

        self._write_log(branch_name, delete_local, delete_remote, backup_tag, errors)

        return DeletionResult(
            branch_name=branch_name,
            local_deleted=local_deleted,
            remote_deleted=remote_deleted,
            backup_tag=backup_tag,
            errors=errors,
        )

    def _safety_check(self, branch_name: str, repo: Repo) -> None:
        try:
            active = repo.active_branch.name
            if branch_name == active:
                raise ValueError(f"Cannot delete active branch (HEAD): '{branch_name}'")
        except TypeError:
            # Detached HEAD — no active branch, safe to proceed
            pass

    def _create_backup_tag(self, branch_name: str, repo: Repo) -> str:
        date_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
        safe_name = branch_name.replace("/", "-")
        tag_name = f"backup/{safe_name}-{date_str}"
        branch_heads = [h for h in repo.heads if h.name == branch_name]
        commit = branch_heads[0].commit if branch_heads else repo.head.commit
        repo.create_tag(tag_name, ref=commit)
        return tag_name

    def _write_log(
        self,
        branch_name: str,
        delete_local: bool,
        delete_remote: bool,
        backup_tag: str | None,
        errors: list[str],
    ) -> None:
        try:
            log_file = _log_path()
            log_file.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "branch": branch_name,
                "delete_local": delete_local,
                "delete_remote": delete_remote,
                "backup_tag": backup_tag,
                "errors": errors,
            }
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning("Failed to write deletion log: %s", e)
