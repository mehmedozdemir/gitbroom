from datetime import datetime, timezone

import pytest

from gitbroom.core.models import (
    AppSettings,
    BranchInfo,
    DeletionResult,
    MergeType,
    RiskLevel,
    RiskScore,
)


def _make_risk_score(level: RiskLevel = RiskLevel.GREEN) -> RiskScore:
    labels = {
        RiskLevel.GREEN: ("Güvenli Sil", "🟢"),
        RiskLevel.YELLOW: ("Gözden Geçir", "🟡"),
        RiskLevel.ORANGE: ("Bekle", "🟠"),
        RiskLevel.RED: ("Dokunma", "🔴"),
    }
    label, icon = labels[level]
    return RiskScore(level=level, label=label, icon=icon)


def _make_branch_info(**kwargs) -> BranchInfo:
    defaults: dict = dict(
        name="feature/test",
        is_local=True,
        is_remote=False,
        last_commit_sha="abc123",
        last_commit_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        last_commit_author="Alice",
        last_commit_message="initial commit",
        is_merged=False,
        merge_type=MergeType.NOT_MERGED,
        merged_at=None,
        merged_into=None,
        ahead_count=0,
        behind_count=0,
        risk_score=_make_risk_score(),
    )
    defaults.update(kwargs)
    return BranchInfo(**defaults)


class TestRiskLevel:
    def test_all_levels_exist(self):
        assert RiskLevel.GREEN.value == "green"
        assert RiskLevel.YELLOW.value == "yellow"
        assert RiskLevel.ORANGE.value == "orange"
        assert RiskLevel.RED.value == "red"


class TestMergeType:
    def test_all_types_exist(self):
        assert MergeType.STANDARD.value == "merge"
        assert MergeType.SQUASH.value == "squash"
        assert MergeType.REBASE.value == "rebase"
        assert MergeType.UNKNOWN.value == "unknown"
        assert MergeType.NOT_MERGED.value == "not_merged"


class TestRiskScore:
    def test_instantiate_minimal(self):
        score = RiskScore(level=RiskLevel.GREEN, label="Güvenli Sil", icon="🟢")
        assert score.level == RiskLevel.GREEN
        assert score.reasons == []

    def test_instantiate_with_reasons(self):
        score = RiskScore(
            level=RiskLevel.RED,
            label="Dokunma",
            icon="🔴",
            reasons=["Açık MR var"],
        )
        assert len(score.reasons) == 1


class TestBranchInfo:
    def test_instantiate_minimal(self):
        branch = _make_branch_info()
        assert branch.name == "feature/test"
        assert branch.gitlab_mr_id is None
        assert branch.gitlab_mr_state is None
        assert branch.gitlab_mr_author is None
        assert branch.risk_reasons == []

    def test_instantiate_with_gitlab_fields(self):
        branch = _make_branch_info(
            gitlab_mr_id=42,
            gitlab_mr_state="opened",
            gitlab_mr_author="bob",
        )
        assert branch.gitlab_mr_id == 42
        assert branch.gitlab_mr_state == "opened"

    def test_merged_branch(self):
        branch = _make_branch_info(
            is_merged=True,
            merge_type=MergeType.STANDARD,
            merged_into="main",
            merged_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        assert branch.is_merged is True
        assert branch.merged_into == "main"

    def test_local_and_remote(self):
        branch = _make_branch_info(is_local=True, is_remote=True)
        assert branch.is_local and branch.is_remote


class TestDeletionResult:
    def test_instantiate_success(self):
        result = DeletionResult(
            branch_name="feature/old",
            local_deleted=True,
            remote_deleted=True,
            backup_tag="backup/feature-old-20240101",
        )
        assert result.errors == []
        assert result.backup_tag == "backup/feature-old-20240101"

    def test_instantiate_with_errors(self):
        result = DeletionResult(
            branch_name="feature/old",
            local_deleted=False,
            remote_deleted=False,
            backup_tag=None,
            errors=["Remote silme hatası: permission denied"],
        )
        assert len(result.errors) == 1
        assert result.local_deleted is False


class TestAppSettings:
    def test_default_values(self):
        settings = AppSettings()
        assert settings.default_branch == "main"
        assert settings.stale_days_green == 90
        assert settings.stale_days_yellow == 30
        assert settings.stale_days_red == 14
        assert settings.theme == "dark"
        assert settings.gitlab_enabled is False
        assert settings.create_backup_tag is True

    def test_custom_values(self):
        settings = AppSettings(
            default_branch="develop",
            stale_days_green=60,
            theme="light",
        )
        assert settings.default_branch == "develop"
        assert settings.stale_days_green == 60
        assert settings.theme == "light"
