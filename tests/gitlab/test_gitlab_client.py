from __future__ import annotations

import pytest

from gitbroom.gitlab.client import GitLabClient


class TestExtractProjectPath:
    def test_ssh_url(self):
        path = GitLabClient._extract_project_path("git@gitlab.com:group/project.git")
        assert path == "group/project"

    def test_ssh_url_nested_group(self):
        path = GitLabClient._extract_project_path("git@gitlab.com:org/sub/project.git")
        assert path == "org/sub/project"

    def test_https_url(self):
        path = GitLabClient._extract_project_path("https://gitlab.com/group/project.git")
        assert path == "group/project"

    def test_https_url_no_git_suffix(self):
        path = GitLabClient._extract_project_path("https://gitlab.com/group/project")
        assert path == "group/project"

    def test_invalid_url_returns_none(self):
        path = GitLabClient._extract_project_path("not-a-url")
        assert path is None

    def test_self_hosted_https(self):
        path = GitLabClient._extract_project_path("https://gitlab.example.com/team/repo.git")
        assert path == "team/repo"


class TestGitLabClientInit:
    def test_not_connected_initially(self):
        client = GitLabClient("https://gitlab.com", "fake-token")
        assert not client.is_connected()

    def test_connect_fails_gracefully_with_bad_token(self):
        client = GitLabClient("https://gitlab.com", "bad-token")
        result = client.connect("https://gitlab.com/group/repo.git")
        assert result is False
        assert not client.is_connected()

    def test_get_branch_mr_returns_none_when_not_connected(self):
        client = GitLabClient("https://gitlab.com", "token")
        result = client.get_branch_mr("feature/something")
        assert result is None
