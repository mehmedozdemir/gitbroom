from __future__ import annotations

from datetime import datetime, timezone

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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
        self._repo_path: str | None = None
        self._current_branch: BranchInfo | None = None
        self._commit_worker = None
        self._commit_data: list[dict] = []
        self._build_ui()
        self.clear()

    def set_repo_path(self, path: str) -> None:
        self._repo_path = path

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(12)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(container)
        outer.addWidget(scroll, stretch=1)

        # Commit mini-list (pinned at bottom, outside scroll)
        self._commit_section = QWidget()
        commit_layout = QVBoxLayout(self._commit_section)
        commit_layout.setContentsMargins(8, 4, 8, 8)
        commit_layout.setSpacing(4)

        hdr_row = QWidget()
        hdr_layout = QHBoxLayout(hdr_row)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        self._commit_section_label = QLabel("SON COMMİTLER")
        self._commit_section_label.setStyleSheet(
            "color: #89b4fa; font-weight: bold; font-size: 11px; letter-spacing: 1px;"
        )
        self._commit_status_label = QLabel("")
        self._commit_status_label.setStyleSheet("color: #6c6f85; font-size: 10px;")
        hdr_layout.addWidget(self._commit_section_label)
        hdr_layout.addStretch()
        hdr_layout.addWidget(self._commit_status_label)
        commit_layout.addWidget(hdr_row)

        self._commit_list = QListWidget()
        self._commit_list.setMaximumHeight(130)
        self._commit_list.setFrameShape(QFrame.Shape.NoFrame)
        self._commit_list.setStyleSheet("font-size: 11px;")
        self._commit_list.itemDoubleClicked.connect(self._on_commit_double_clicked)
        commit_layout.addWidget(self._commit_list)

        outer.addWidget(self._commit_section)
        self._commit_section.setVisible(False)

    def clear(self) -> None:
        self._clear_layout()
        self._current_branch = None
        self._commit_section.setVisible(False)
        placeholder = QLabel("Branch seçin")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #6c6f85; font-size: 13px;")
        self._layout.addWidget(placeholder)

    def show_branch(self, branch: BranchInfo) -> None:
        self._current_branch = branch
        self._clear_layout()
        self._add_header(branch)
        self._add_risk_badge(branch)
        self._add_commit_info(branch)
        self._add_merge_info(branch)
        self._add_ahead_behind(branch)
        if branch.gitlab_mr_id:
            self._add_gitlab_info(branch)
        self._layout.addStretch()
        self._load_commits(branch)

    # ── Commit mini-list ─────────────────────────────────────────────────────

    def _load_commits(self, branch: BranchInfo) -> None:
        if not self._repo_path:
            return
        from gitbroom.ui.workers import CommitLoader
        if self._commit_worker and self._commit_worker.isRunning():
            self._commit_worker.terminate()
            self._commit_worker.wait()

        self._commit_list.clear()
        self._commit_status_label.setText("yükleniyor…")
        self._commit_section.setVisible(True)

        self._commit_worker = CommitLoader(self._repo_path, branch.name, max_count=5)
        self._commit_worker.commits_loaded.connect(self._on_commits_loaded)
        self._commit_worker.error.connect(self._on_commits_error)
        self._commit_worker.start()

    def _on_commits_loaded(self, commits: list) -> None:
        self._commit_data = commits
        self._commit_list.clear()
        self._commit_status_label.setText(f"{len(commits)} commit")

        for c in commits:
            date_str = c["date"].strftime("%d.%m.%y")
            text = f"{c['short_sha']}  {c['message'][:40]}  · {c['author'][:18]}  {date_str}"
            item = QListWidgetItem(text)
            item.setToolTip(c["message"])
            item.setData(Qt.ItemDataRole.UserRole, c)
            self._commit_list.addItem(item)

    def _on_commits_error(self, _message: str) -> None:
        self._commit_status_label.setText("yüklenemedi")

    def _on_commit_double_clicked(self, item: QListWidgetItem) -> None:
        commit = item.data(Qt.ItemDataRole.UserRole)
        if not commit or not self._repo_path:
            return
        from gitbroom.ui.widgets.commit_detail_dialog import CommitDetailDialog
        dlg = CommitDetailDialog(
            repo_path=self._repo_path,
            commit_sha=commit["sha"],
            short_sha=commit["short_sha"],
            commit_message=commit["message"],
            author=commit["author"],
            parent_widget=self,
        )
        dlg.exec()

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
