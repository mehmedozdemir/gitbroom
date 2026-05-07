from __future__ import annotations

import logging

from gitbroom.core.models import BranchInfo
from gitbroom.gitlab.client import GitLabClient

logger = logging.getLogger(__name__)


class BranchEnricher:
    def __init__(self, client: GitLabClient) -> None:
        self._client = client

    def enrich(self, branches: list[BranchInfo]) -> list[BranchInfo]:
        """Add GitLab MR data to each branch. Failures are silently ignored."""
        if not self._client.is_connected():
            return branches

        for branch in branches:
            try:
                mr = self._client.get_branch_mr(branch.name)
                if mr:
                    branch.gitlab_mr_id = mr["id"]
                    branch.gitlab_mr_state = mr["state"]
                    branch.gitlab_mr_author = mr["author"]
            except Exception as e:
                logger.debug("Enrichment skipped for %s: %s", branch.name, e)

        return branches
