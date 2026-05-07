from __future__ import annotations

from datetime import datetime, timezone

import pytest

from gitbroom.core.models import BranchInfo, MergeType, RiskLevel, RiskScore
from gitbroom.ui.models.branch_table_model import BranchTableModel


def _make_branch(
    name: str = "feature/test",
    is_merged: bool = False,
    risk_level: RiskLevel = RiskLevel.GREEN,
    author: str = "Alice",
    days_old: int = 100,
) -> BranchInfo:
    from datetime import timedelta
    score = RiskScore(level=risk_level, label="Güvenli Sil", icon="🟢")
    return BranchInfo(
        name=name,
        is_local=True,
        is_remote=False,
        last_commit_sha="a" * 40,
        last_commit_date=datetime.now(tz=timezone.utc) - timedelta(days=days_old),
        last_commit_author=author,
        last_commit_message="test commit",
        is_merged=is_merged,
        merge_type=MergeType.STANDARD if is_merged else MergeType.NOT_MERGED,
        merged_at=None,
        merged_into="main" if is_merged else None,
        ahead_count=0,
        behind_count=0,
        risk_score=score,
    )


@pytest.fixture
def branches() -> list[BranchInfo]:
    return [
        _make_branch("feature/a", is_merged=True, risk_level=RiskLevel.GREEN),
        _make_branch("feature/b", is_merged=False, risk_level=RiskLevel.RED, days_old=5),
        _make_branch("fix/c", is_merged=True, risk_level=RiskLevel.YELLOW, author="Bob"),
    ]


@pytest.fixture
def model(branches, qtbot) -> BranchTableModel:
    m = BranchTableModel(branches)
    return m


class TestRowAndColumnCounts:
    def test_row_count_matches_branches(self, model, branches):
        assert model.rowCount() == len(branches)

    def test_column_count_is_seven(self, model):
        assert model.columnCount() == 7

    def test_empty_model_has_zero_rows(self, qtbot):
        m = BranchTableModel()
        assert m.rowCount() == 0


class TestHeaderData:
    def test_headers_are_correct(self, model):
        from PyQt6.QtCore import Qt
        headers = [model.headerData(i, Qt.Orientation.Horizontal) for i in range(7)]
        assert headers[1] == "Branch"
        assert headers[2] == "Yazar"
        assert headers[5] == "Risk"


class TestDisplayData:
    def test_branch_name_in_column_1(self, model, branches):
        from PyQt6.QtCore import QModelIndex, Qt
        idx = model.index(0, 1)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == branches[0].name

    def test_author_in_column_2(self, model):
        from PyQt6.QtCore import Qt
        idx = model.index(0, 2)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "Alice"

    def test_merge_status_merged(self, model):
        from PyQt6.QtCore import Qt
        idx = model.index(0, 4)  # feature/a is merged
        assert "✅" in model.data(idx, Qt.ItemDataRole.DisplayRole)

    def test_merge_status_unmerged(self, model):
        from PyQt6.QtCore import Qt
        idx = model.index(1, 4)  # feature/b is not merged
        assert "⚠️" in model.data(idx, Qt.ItemDataRole.DisplayRole)

    def test_risk_column_has_icon(self, model):
        from PyQt6.QtCore import Qt
        idx = model.index(0, 5)
        assert "🟢" in model.data(idx, Qt.ItemDataRole.DisplayRole)

    def test_location_local_only(self, model):
        from PyQt6.QtCore import Qt
        idx = model.index(0, 6)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "Local"


class TestCheckbox:
    def test_unchecked_by_default(self, model):
        from PyQt6.QtCore import Qt
        idx = model.index(0, 0)
        state = model.data(idx, Qt.ItemDataRole.CheckStateRole)
        assert state == Qt.CheckState.Unchecked.value

    def test_check_branch(self, model):
        from PyQt6.QtCore import Qt
        idx = model.index(0, 0)
        model.setData(idx, Qt.CheckState.Checked.value, Qt.ItemDataRole.CheckStateRole)
        state = model.data(idx, Qt.ItemDataRole.CheckStateRole)
        assert state == Qt.CheckState.Checked.value

    def test_checked_branches_returns_selected(self, model):
        from PyQt6.QtCore import Qt
        idx = model.index(0, 0)
        model.setData(idx, Qt.CheckState.Checked.value, Qt.ItemDataRole.CheckStateRole)
        checked = model.checked_branches()
        assert len(checked) == 1
        assert checked[0].name == "feature/a"

    def test_check_all(self, model, branches):
        model.check_all(True)
        assert len(model.checked_branches()) == len(branches)

    def test_uncheck_all(self, model):
        model.check_all(True)
        model.check_all(False)
        assert model.checked_branches() == []


class TestFilter:
    def test_filter_by_text(self, model):
        model.filter(text="fix")
        assert model.rowCount() == 1

    def test_filter_by_author(self, model):
        model.filter(text="bob")
        assert model.rowCount() == 1

    def test_filter_merged_only(self, model):
        model.filter(show_merged=True)
        assert model.rowCount() == 2

    def test_filter_unmerged_only(self, model):
        model.filter(show_merged=False)
        assert model.rowCount() == 1

    def test_clear_filter(self, model, branches):
        model.filter(text="zzznomatch")
        assert model.rowCount() == 0
        model.filter()
        assert model.rowCount() == len(branches)


class TestSetBranches:
    def test_set_branches_replaces_data(self, model, qtbot):
        new = [_make_branch("new/branch")]
        model.set_branches(new)
        assert model.rowCount() == 1
        from PyQt6.QtCore import Qt
        idx = model.index(0, 1)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "new/branch"
