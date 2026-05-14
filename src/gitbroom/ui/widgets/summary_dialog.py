from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gitbroom.core.models import BranchInfo, RiskLevel


def _relative_long(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    days = (datetime.now(tz=timezone.utc) - dt).days
    if days < 30:
        return f"{days} gün"
    months = days // 30
    years, rem_m = divmod(months, 12)
    if years and rem_m:
        return f"{years} yıl {rem_m} ay"
    if years:
        return f"{years} yıl"
    return f"{months} ay"


def build_summary(branches: list[BranchInfo], repo_name: str = "") -> str:
    if not branches:
        return "Branch bulunamadı."

    total = len(branches)
    risk_counts = Counter(b.risk_score.level for b in branches)
    merged = sum(1 for b in branches if b.is_merged)
    unmerged = total - merged

    local_only = sum(1 for b in branches if b.is_local and not b.is_remote)
    remote_only = sum(1 for b in branches if b.is_remote and not b.is_local)
    both = sum(1 for b in branches if b.is_local and b.is_remote)

    now = datetime.now(tz=timezone.utc)

    oldest = min(branches, key=lambda b: b.last_commit_date)
    oldest_age = _relative_long(oldest.last_commit_date)

    author_counts: Counter[str] = Counter(b.last_commit_author for b in branches)
    top_author, top_count = author_counts.most_common(1)[0]

    safe_count = risk_counts.get(RiskLevel.GREEN, 0)
    review_count = risk_counts.get(RiskLevel.YELLOW, 0)
    wait_count = risk_counts.get(RiskLevel.ORANGE, 0)
    danger_count = risk_counts.get(RiskLevel.RED, 0)

    date_str = now.strftime("%d.%m.%Y %H:%M")
    title = f"📊 Tarama Özeti{' — ' + repo_name if repo_name else ''}"

    def pct(n: int) -> str:
        return f"{round(n / total * 100)}%" if total else "0%"

    lines = [
        title,
        f"Tarih: {date_str}",
        "",
        f"Toplam Branch     : {total}",
        f"  🟢 Güvenli Sil  : {safe_count:<4} ({pct(safe_count)})",
        f"  🟡 Gözden Geçir : {review_count:<4} ({pct(review_count)})",
        f"  🟠 Bekle        : {wait_count:<4} ({pct(wait_count)})",
        f"  🔴 Dokunma      : {danger_count:<4} ({pct(danger_count)})",
        "",
        "Merge Durumu",
        f"  ✅ Merge edilmiş : {merged}",
        f"  ⚠️  Unmerged     : {unmerged}",
        "",
        "Konum",
        f"  Local + Remote  : {both}",
        f"  Yalnız Local    : {local_only}",
        f"  Yalnız Remote   : {remote_only}",
        "",
        f"En Eski Branch    : {oldest.name}  ({oldest_age} önce)",
        f"En Aktif Yazar    : {top_author}  ({top_count} branch)",
    ]

    if safe_count:
        lines.append(f"\n💡 {safe_count} branch güvenli silinebilir.")
    if danger_count:
        lines.append(f"⚠️  {danger_count} branch aktif — dokunmayın.")

    return "\n".join(lines)


class SummaryDialog(QDialog):
    def __init__(
        self,
        branches: list[BranchInfo],
        repo_name: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._text = build_summary(branches, repo_name)
        self.setWindowTitle("Tarama Özeti")
        self.setMinimumSize(520, 420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._editor = QPlainTextEdit(self._text)
        self._editor.setReadOnly(True)
        self._editor.setFont(self._editor.font())
        layout.addWidget(self._editor)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self._copy_status = QLabel("")
        btn_layout.addWidget(self._copy_status)
        btn_layout.addStretch()

        btn_copy = QPushButton("📋  Kopyala")
        btn_copy.clicked.connect(self._on_copy)
        btn_layout.addWidget(btn_copy)

        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addWidget(btn_row)

    def _on_copy(self) -> None:
        QApplication.clipboard().setText(self._text)
        self._copy_status.setText("✓ Panoya kopyalandı")
