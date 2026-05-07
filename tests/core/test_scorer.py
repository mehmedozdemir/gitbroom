from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from gitbroom.core.models import AppSettings, BranchInfo, MergeType, RiskLevel, RiskScore
from gitbroom.core.scorer import RiskScorer


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _days_ago(n: int) -> datetime:
    return _now() - timedelta(days=n)


def _make_branch(
    *,
    is_merged: bool = False,
    days_old: int = 100,
    merge_type: MergeType = MergeType.NOT_MERGED,
    gitlab_mr_state: str | None = None,
    gitlab_mr_id: int | None = None,
) -> BranchInfo:
    placeholder = RiskScore(level=RiskLevel.ORANGE, label="Bekle", icon="🟠")
    return BranchInfo(
        name="test/branch",
        is_local=True,
        is_remote=False,
        last_commit_sha="abc" * 13 + "a",
        last_commit_date=_days_ago(days_old),
        last_commit_author="Author",
        last_commit_message="some commit",
        is_merged=is_merged,
        merge_type=merge_type if is_merged else MergeType.NOT_MERGED,
        merged_at=_days_ago(days_old) if is_merged else None,
        merged_into="main" if is_merged else None,
        ahead_count=0,
        behind_count=0,
        risk_score=placeholder,
        gitlab_mr_state=gitlab_mr_state,
        gitlab_mr_id=gitlab_mr_id,
    )


@pytest.fixture
def default_settings() -> AppSettings:
    return AppSettings()  # green=90, yellow=30, red=14


@pytest.fixture
def scorer(default_settings) -> RiskScorer:
    return RiskScorer(default_settings)


class TestRedRule:
    def test_active_commit_within_red_threshold_is_red(self, scorer):
        branch = _make_branch(is_merged=False, days_old=5)
        result = scorer.score(branch)
        assert result.level == RiskLevel.RED

    def test_commit_exactly_at_red_threshold_is_red(self, scorer):
        # days_old=13 → still within 14-day window
        branch = _make_branch(is_merged=False, days_old=13)
        result = scorer.score(branch)
        assert result.level == RiskLevel.RED

    def test_commit_at_red_boundary_not_red(self, scorer):
        # days_old=14 → exactly at threshold, NOT within last 14 days
        branch = _make_branch(is_merged=False, days_old=14)
        result = scorer.score(branch)
        assert result.level != RiskLevel.RED

    def test_open_mr_is_red(self, scorer):
        branch = _make_branch(is_merged=False, days_old=90, gitlab_mr_state="opened", gitlab_mr_id=42)
        result = scorer.score(branch)
        assert result.level == RiskLevel.RED

    def test_closed_mr_does_not_trigger_red(self, scorer):
        branch = _make_branch(is_merged=True, days_old=100, gitlab_mr_state="merged", gitlab_mr_id=42)
        result = scorer.score(branch)
        assert result.level == RiskLevel.GREEN


class TestGreenRule:
    def test_merged_old_branch_is_green(self, scorer):
        branch = _make_branch(is_merged=True, days_old=91)
        result = scorer.score(branch)
        assert result.level == RiskLevel.GREEN

    def test_merged_exactly_90_days_is_green(self, scorer):
        branch = _make_branch(is_merged=True, days_old=90)
        result = scorer.score(branch)
        assert result.level == RiskLevel.GREEN

    def test_merged_89_days_is_not_green(self, scorer):
        branch = _make_branch(is_merged=True, days_old=89)
        result = scorer.score(branch)
        assert result.level != RiskLevel.GREEN


class TestYellowRule:
    def test_merged_between_30_and_90_days_is_yellow(self, scorer):
        branch = _make_branch(is_merged=True, days_old=60)
        result = scorer.score(branch)
        assert result.level == RiskLevel.YELLOW

    def test_merged_exactly_30_days_is_yellow(self, scorer):
        branch = _make_branch(is_merged=True, days_old=30)
        result = scorer.score(branch)
        assert result.level == RiskLevel.YELLOW

    def test_unmerged_older_than_60_days_is_yellow(self, scorer):
        branch = _make_branch(is_merged=False, days_old=65)
        result = scorer.score(branch)
        assert result.level == RiskLevel.YELLOW

    def test_unmerged_exactly_60_days_is_yellow(self, scorer):
        branch = _make_branch(is_merged=False, days_old=60)
        result = scorer.score(branch)
        assert result.level == RiskLevel.YELLOW


class TestOrangeRule:
    def test_merged_within_30_days_is_orange(self, scorer):
        branch = _make_branch(is_merged=True, days_old=20)
        result = scorer.score(branch)
        assert result.level == RiskLevel.ORANGE

    def test_unmerged_between_14_and_60_days_is_orange(self, scorer):
        branch = _make_branch(is_merged=False, days_old=40)
        result = scorer.score(branch)
        assert result.level == RiskLevel.ORANGE


class TestReasons:
    def test_score_always_has_reason(self, scorer):
        for days, merged in [(5, False), (100, True), (60, True), (65, False), (40, False)]:
            branch = _make_branch(is_merged=merged, days_old=days)
            result = scorer.score(branch)
            assert len(result.reasons) > 0, f"No reason for days={days}, merged={merged}"


class TestCustomThresholds:
    def test_custom_green_threshold(self):
        settings = AppSettings(stale_days_green=60, stale_days_yellow=20, stale_days_red=7)
        scorer = RiskScorer(settings)
        branch = _make_branch(is_merged=True, days_old=65)
        result = scorer.score(branch)
        assert result.level == RiskLevel.GREEN

    def test_custom_red_threshold(self):
        settings = AppSettings(stale_days_green=90, stale_days_yellow=30, stale_days_red=7)
        scorer = RiskScorer(settings)
        # days_old=6 → within 7-day red window
        branch = _make_branch(is_merged=False, days_old=6)
        result = scorer.score(branch)
        assert result.level == RiskLevel.RED

    def test_commit_outside_custom_red_threshold(self):
        settings = AppSettings(stale_days_green=90, stale_days_yellow=30, stale_days_red=7)
        scorer = RiskScorer(settings)
        # days_old=8 → outside 7-day window
        branch = _make_branch(is_merged=False, days_old=8)
        result = scorer.score(branch)
        assert result.level != RiskLevel.RED
