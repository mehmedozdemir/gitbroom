from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class GitLabClient:
    def __init__(self, url: str, token: str) -> None:
        self._url = url
        self._token = token
        self._gl = None
        self._project = None

    def connect(self, remote_url: str) -> bool:
        """Authenticate and locate the project from remote URL. Returns False on any failure."""
        try:
            import gitlab  # type: ignore
            self._gl = gitlab.Gitlab(self._url, private_token=self._token)
            self._gl.auth()
            project_path = self._extract_project_path(remote_url)
            if not project_path:
                logger.warning("Could not extract project path from: %s", remote_url)
                return False
            self._project = self._gl.projects.get(project_path)
            return True
        except Exception as e:
            logger.warning("GitLab connection failed: %s", e)
            self._gl = None
            self._project = None
            return False

    def get_branch_mr(self, branch_name: str) -> dict | None:
        """Return open MR info for the given branch, or None."""
        if not self._project:
            return None
        try:
            mrs = self._project.mergerequests.list(
                source_branch=branch_name,
                state="opened",
                get_all=False,
                per_page=1,
            )
            if not mrs:
                return None
            mr = mrs[0]
            return {
                "id": mr.iid,
                "state": mr.state,
                "author": mr.author.get("username", "") if isinstance(mr.author, dict) else "",
                "title": mr.title,
            }
        except Exception as e:
            logger.debug("MR fetch failed for %s: %s", branch_name, e)
            return None

    def is_connected(self) -> bool:
        return self._project is not None

    @staticmethod
    def _extract_project_path(remote_url: str) -> str | None:
        """
        git@gitlab.com:group/project.git  → group/project
        https://gitlab.com/group/project  → group/project
        """
        # SSH form
        ssh = re.match(r"git@[^:]+:(.+?)(?:\.git)?$", remote_url)
        if ssh:
            return ssh.group(1)
        # HTTPS form
        https = re.match(r"https?://[^/]+/(.+?)(?:\.git)?$", remote_url)
        if https:
            return https.group(1)
        return None
