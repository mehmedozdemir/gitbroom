from __future__ import annotations

from datetime import datetime, timezone

from gitbroom.core.models import AppSettings, BranchInfo, RiskLevel, RiskScore


class RiskScorer:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def score(self, branch: BranchInfo) -> RiskScore:
        """
        Rule priority (first match wins):
        1. Active commit in last stale_days_red days  → RED
        2. Has open MR (GitLab)                       → RED
        3. Merged + commit older than stale_days_green → GREEN
        4. Merged + commit older than stale_days_yellow → YELLOW
        5. Merged + commit within stale_days_yellow   → ORANGE
        6. Unmerged + commit older than stale_days_yellow * 2 → YELLOW
        7. Default                                    → ORANGE
        """
        s = self._settings
        age_days = self._days_since(branch.last_commit_date)
        reasons: list[str] = []

        # Rule 1 — recently active
        if age_days < s.stale_days_red:
            reasons.append(f"Son {s.stale_days_red} günde aktif commit var ({age_days} gün önce)")
            return RiskScore(level=RiskLevel.RED, label="Dokunma", icon="🔴", reasons=reasons)

        # Rule 2 — open MR
        if branch.gitlab_mr_state == "opened":
            reasons.append(f"Açık MR var (#{branch.gitlab_mr_id})")
            return RiskScore(level=RiskLevel.RED, label="Dokunma", icon="🔴", reasons=reasons)

        if branch.is_merged:
            # Rule 3 — merged + old enough
            if age_days >= s.stale_days_green:
                reasons.append(
                    f"Merge edilmiş ve son commit {age_days} gün önce "
                    f"(eşik: {s.stale_days_green} gün)"
                )
                return RiskScore(
                    level=RiskLevel.GREEN, label="Güvenli Sil", icon="🟢", reasons=reasons
                )

            # Rule 4 — merged + moderately old
            if age_days >= s.stale_days_yellow:
                reasons.append(
                    f"Merge edilmiş, son commit {age_days} gün önce "
                    f"({s.stale_days_yellow}–{s.stale_days_green} gün arası)"
                )
                return RiskScore(
                    level=RiskLevel.YELLOW, label="Gözden Geçir", icon="🟡", reasons=reasons
                )

            # Rule 5 — merged but recent
            reasons.append(
                f"Merge edilmiş ama son commit yalnızca {age_days} gün önce"
            )
            return RiskScore(level=RiskLevel.ORANGE, label="Bekle", icon="🟠", reasons=reasons)

        # Rule 6 — unmerged + stale
        stale_threshold = s.stale_days_yellow * 2  # default: 60 days
        if age_days >= stale_threshold:
            reasons.append(
                f"Merge edilmemiş ve {age_days} gün boyunca hareketsiz "
                f"(eşik: {stale_threshold} gün)"
            )
            return RiskScore(
                level=RiskLevel.YELLOW, label="Gözden Geçir", icon="🟡", reasons=reasons
            )

        # Rule 7 — default
        reasons.append(f"Merge edilmemiş, son commit {age_days} gün önce")
        return RiskScore(level=RiskLevel.ORANGE, label="Bekle", icon="🟠", reasons=reasons)

    @staticmethod
    def _days_since(dt: datetime) -> int:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(tz=timezone.utc) - dt
        return delta.days
