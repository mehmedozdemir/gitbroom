from __future__ import annotations

from datetime import datetime, timezone

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gitbroom.core.models import BranchInfo, RiskLevel

_RISK_COLORS: dict[RiskLevel, str] = {
    RiskLevel.GREEN:  "#a6e3a1",
    RiskLevel.YELLOW: "#f9e2af",
    RiskLevel.ORANGE: "#fab387",
    RiskLevel.RED:    "#f38ba8",
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


def _initials(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if name else "?"


class BranchDetailPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(420)
        self._build_ui()
        self.clear()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(12)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(container)
        outer.addWidget(scroll)

    def clear(self) -> None:
        self._clear_layout()
        placeholder = QLabel("Branch seçin")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #6c6f85; font-size: 13px;")
        self._layout.addWidget(placeholder)

    def show_branch(self, branch: BranchInfo) -> None:
        self._clear_layout()
        self._add_header(branch)
        self._add_risk_badge(branch)
        self._add_commit_info(branch)
        self._add_merge_info(branch)
        self._add_ahead_behind(branch)
        if branch.gitlab_mr_id:
            self._add_gitlab_info(branch)
        self._layout.addStretch()

    # ── Section builders ─────────────────────────────────────────────────────

    def _add_header(self, branch: BranchInfo) -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        avatar = QLabel(_initials(branch.last_commit_author))
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color = _RISK_COLORS.get(branch.risk_score.level, "#89b4fa")
        avatar.setStyleSheet(
            f"background-color: {color}; color: #1e1e2e; "
            "border-radius: 20px; font-weight: bold; font-size: 14px;"
        )
        layout.addWidget(avatar)

        name_label = QLabel(branch.name)
        name_label.setWordWrap(True)
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(name_label, stretch=1)

        self._layout.addWidget(row)

    def _add_risk_badge(self, branch: BranchInfo) -> None:
        color = _RISK_COLORS.get(branch.risk_score.level, "#89b4fa")
        badge = QLabel(f"{branch.risk_score.icon}  {branch.risk_score.label}")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background-color: {color}22; color: {color}; "
            "border: 1px solid " + color + "; border-radius: 6px; "
            "padding: 6px 12px; font-weight: bold;"
        )
        self._layout.addWidget(badge)

        if branch.risk_score.reasons:
            reasons_text = "\n".join(f"• {r}" for r in branch.risk_score.reasons)
            reasons_label = QLabel(reasons_text)
            reasons_label.setWordWrap(True)
            reasons_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
            self._layout.addWidget(reasons_label)

    def _add_commit_info(self, branch: BranchInfo) -> None:
        self._layout.addWidget(self._section_header("Son Commit"))

        sha_short = branch.last_commit_sha[:8]
        info = QLabel(
            f"<b>{sha_short}</b> — {_relative_time(branch.last_commit_date)}<br>"
            f"<span style='color:#a6adc8'>{branch.last_commit_author}</span><br>"
            f"{branch.last_commit_message}"
        )
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setStyleSheet("font-size: 12px;")
        self._layout.addWidget(info)

    def _add_merge_info(self, branch: BranchInfo) -> None:
        self._layout.addWidget(self._section_header("Merge Durumu"))

        if branch.is_merged:
            merge_type = branch.merge_type.value if branch.merge_type else "bilinmiyor"
            merged_into = branch.merged_into or "—"
            merged_at = _relative_time(branch.merged_at) if branch.merged_at else "—"
            text = (
                f"✅ Merge edildi ({merge_type})<br>"
                f"<span style='color:#a6adc8'>Hedef:</span> {merged_into}<br>"
                f"<span style='color:#a6adc8'>Tarih:</span> {merged_at}"
            )
        else:
            text = "⚠️ Henüz merge edilmemiş"

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setStyleSheet("font-size: 12px;")
        self._layout.addWidget(label)

    def _add_ahead_behind(self, branch: BranchInfo) -> None:
        self._layout.addWidget(self._section_header("Default Branch'e Göre"))

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        ahead = QLabel(f"↑ {branch.ahead_count} ahead")
        ahead.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        behind = QLabel(f"↓ {branch.behind_count} behind")
        behind.setStyleSheet("color: #f38ba8; font-weight: bold;")

        layout.addWidget(ahead)
        layout.addWidget(behind)
        layout.addStretch()
        self._layout.addWidget(row)

    def _add_gitlab_info(self, branch: BranchInfo) -> None:
        self._layout.addWidget(self._section_header("GitLab MR"))
        state_color = "#a6e3a1" if branch.gitlab_mr_state != "opened" else "#f38ba8"
        text = (
            f"MR #{branch.gitlab_mr_id}<br>"
            f"<span style='color:{state_color}'>{branch.gitlab_mr_state or '—'}</span><br>"
            f"Yazar: {branch.gitlab_mr_author or '—'}"
        )
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 12px;")
        self._layout.addWidget(label)

    def _section_header(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            "color: #89b4fa; font-weight: bold; font-size: 11px; "
            "text-transform: uppercase; letter-spacing: 1px; "
            "border-bottom: 1px solid #313244; padding-bottom: 2px;"
        )
        return label

    def _clear_layout(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
