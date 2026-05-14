from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RiskLevel(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


class MergeType(Enum):
    STANDARD = "merge"
    SQUASH = "squash"
    REBASE = "rebase"
    UNKNOWN = "unknown"
    NOT_MERGED = "not_merged"


@dataclass
class RiskScore:
    level: RiskLevel
    label: str
    icon: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class BranchInfo:
    name: str
    is_local: bool
    is_remote: bool
    last_commit_sha: str
    last_commit_date: datetime
    last_commit_author: str
    last_commit_author_email: str
    last_commit_message: str
    is_merged: bool
    merge_type: MergeType
    merged_at: datetime | None
    merged_into: str | None
    ahead_count: int
    behind_count: int
    risk_score: RiskScore
    risk_reasons: list[str] = field(default_factory=list)
    gitlab_mr_id: int | None = None
    gitlab_mr_state: str | None = None
    gitlab_mr_author: str | None = None


@dataclass
class DeletionResult:
    branch_name: str
    local_deleted: bool
    remote_deleted: bool
    backup_tag: str | None
    errors: list[str] = field(default_factory=list)


_DEFAULT_PROTECTED_BRANCHES: list[str] = [
    "main", "master", "develop", "development", "dev",
    "staging", "stage", "preprod", "pre-prod", "production", "prod",
    "release", "hotfix", "test", "testing", "qa", "uat",
]


@dataclass
class AppSettings:
    default_branch: str = "main"
    stale_days_green: int = 90
    stale_days_yellow: int = 30
    stale_days_red: int = 14
    theme: str = "dark"
    language: str = "tr"
    gitlab_enabled: bool = False
    gitlab_url: str = "https://gitlab.com"
    gitlab_token: str = ""
    create_backup_tag: bool = True
    confirm_remote_delete: bool = True
    show_merged_by_default: bool = True
    enable_rebase_detection: bool = False
    protected_branches: list[str] = field(default_factory=lambda: list(_DEFAULT_PROTECTED_BRANCHES))
