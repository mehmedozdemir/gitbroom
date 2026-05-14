from __future__ import annotations

from datetime import datetime, timezone

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor

from gitbroom.core.models import BranchInfo, RiskLevel

_COLUMNS = ["", "Branch", "Yazar", "Son Commit", "Merge", "Risk", "Konum"]

_RISK_COLORS: dict[RiskLevel, tuple[int, int, int, int]] = {
    RiskLevel.GREEN:  (166, 227, 161, 25),
    RiskLevel.YELLOW: (249, 226, 175, 25),
    RiskLevel.ORANGE: (250, 179, 135, 25),
    RiskLevel.RED:    (243, 139, 168, 40),
}


def _relative_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(tz=timezone.utc) - dt
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        return f"{hours} saat önce" if hours > 0 else "az önce"
    if days < 30:
        return f"{days} gün önce"
    months = days // 30
    if months < 12:
        return f"{months} ay önce"
    return f"{days // 365} yıl önce"


class BranchTableModel(QAbstractTableModel):
    def __init__(self, branches: list[BranchInfo] | None = None) -> None:
        super().__init__()
        self._branches: list[BranchInfo] = branches or []
        self._filtered: list[BranchInfo] = list(self._branches)
        self._checked: set[str] = set()

    # ── QAbstractTableModel interface ────────────────────────────────────────

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._filtered)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        branch = self._filtered[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(branch, col)

        if role == Qt.ItemDataRole.CheckStateRole and col == 0:
            state = Qt.CheckState.Checked if branch.name in self._checked else Qt.CheckState.Unchecked
            return state.value

        if role == Qt.ItemDataRole.BackgroundRole:
            r, g, b, a = _RISK_COLORS.get(branch.risk_score.level, (0, 0, 0, 0))
            return QColor(r, g, b, a)

        if role == Qt.ItemDataRole.ToolTipRole:
            return "\n".join(branch.risk_score.reasons) if branch.risk_score.reasons else None

        if role == Qt.ItemDataRole.UserRole:
            return branch

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:
            base |= Qt.ItemFlag.ItemIsUserCheckable
        return base

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            branch = self._filtered[index.row()]
            if value == Qt.CheckState.Checked.value:
                self._checked.add(branch.name)
            else:
                self._checked.discard(branch.name)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    # ── Public API ───────────────────────────────────────────────────────────

    def set_branches(self, branches: list[BranchInfo]) -> None:
        self.beginResetModel()
        self._branches = branches
        self._filtered = list(branches)
        self._checked.clear()
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._branches = []
        self._filtered = []
        self._checked.clear()
        self.endResetModel()

    def add_branch(self, branch: BranchInfo) -> None:
        """Append a single branch — used for streaming results as they arrive."""
        row = len(self._filtered)
        self.beginInsertRows(QModelIndex(), row, row)
        self._branches.append(branch)
        self._filtered.append(branch)
        self.endInsertRows()

    def remove_branches(self, names: set[str]) -> None:
        """Remove branches by name — used after deletion to avoid full rescan."""
        self.beginResetModel()
        self._branches = [b for b in self._branches if b.name not in names]
        self._filtered = [b for b in self._filtered if b.name not in names]
        self._checked -= names
        self.endResetModel()

    def filter(
        self,
        text: str = "",
        show_merged: bool | None = None,
        show_stale: bool | None = None,
        mine_email: str | None = None,
        mine_name: str | None = None,
        local_only: bool = False,
        remote_only: bool = False,
    ) -> None:
        self.beginResetModel()
        self._filtered = [
            b for b in self._branches
            if self._matches(b, text, show_merged, show_stale, mine_email, mine_name, local_only, remote_only)
        ]
        self.endResetModel()

    def checked_branches(self) -> list[BranchInfo]:
        return [b for b in self._filtered if b.name in self._checked]

    def check_all(self, checked: bool) -> None:
        self.beginResetModel()
        if checked:
            self._checked = {b.name for b in self._filtered}
        else:
            self._checked.clear()
        self.endResetModel()

    def branch_at(self, row: int) -> BranchInfo | None:
        if 0 <= row < len(self._filtered):
            return self._filtered[row]
        return None

    # ── Private helpers ──────────────────────────────────────────────────────

    def _display(self, branch: BranchInfo, col: int) -> str | None:
        match col:
            case 0:
                return None
            case 1:
                return branch.name
            case 2:
                return branch.last_commit_author
            case 3:
                return _relative_time(branch.last_commit_date)
            case 4:
                if branch.is_merged:
                    return f"✅ {branch.merge_type.value}"
                return "⚠️ Unmerged"
            case 5:
                return f"{branch.risk_score.icon} {branch.risk_score.label}"
            case 6:
                parts = []
                if branch.is_local:
                    parts.append("Local")
                if branch.is_remote:
                    parts.append("Remote")
                return " + ".join(parts) if parts else "—"
        return None

    def _matches(
        self,
        branch: BranchInfo,
        text: str,
        show_merged: bool | None,
        show_stale: bool | None,
        mine_email: str | None,
        mine_name: str | None,
        local_only: bool,
        remote_only: bool,
    ) -> bool:
        if text:
            needle = text.lower()
            if needle not in branch.name.lower() and needle not in branch.last_commit_author.lower():
                return False
        if show_merged is not None and branch.is_merged != show_merged:
            return False
        if show_stale is True:
            if branch.risk_score.level not in (RiskLevel.GREEN, RiskLevel.YELLOW):
                return False
        if mine_email or mine_name:
            author_email = branch.last_commit_author_email.lower()
            author_name = branch.last_commit_author.lower()
            email_match = bool(mine_email) and bool(author_email) and mine_email.lower() in author_email
            name_match = bool(mine_name) and mine_name.lower() in author_name
            if not email_match and not name_match:
                return False
        if local_only and not branch.is_local:
            return False
        if remote_only and not branch.is_remote:
            return False
        return True
