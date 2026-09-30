from unittest.mock import PropertyMock, patch

import pytest
from github import GithubException, UnknownObjectException

from baldrick.config import loads
from baldrick.github.github_api import FILE_CACHE, IssueHandler, PullRequestHandler, RepoHandler

# TODO: Add more tests to increase coverage.


class TestRepoHandler:
    def setup_class(self):
        self.repo = RepoHandler("fakerepo/doesnotexist", branch="awesomebot")

    def test_get_issues(self, github_api):
        github_api.add(
            "GET",
            "https://api.github.com/repos/fakerepo/doesnotexist/issues",
            [
                {"number": 42, "state": "open"},
                {"number": 55, "state": "open", "pull_request": {"diff_url": "blah"}},
            ],
        )

        assert self.repo.get_issues("open", "Close?") == [42]
        assert self.repo.get_issues("open", "Close?", exclude_pr=False) == [42, 55]
        assert github_api.calls[-1]["parameters"]["labels"] == "Close?"

    def test_get_all_labels(self, github_api):
        github_api.add(
            "GET",
            "https://api.github.com/repos/fakerepo/doesnotexist/labels",
            [{"name": "io.fits"}, {"name": "Documentation"}],
        )

        assert self.repo.get_all_labels() == ["io.fits", "Documentation"]

    def test_missing_ref_not_treated_as_missing_file(self, github_api):
        FILE_CACHE.clear()
        url = "https://api.github.com/repos/fakerepo/doesnotexist/contents/pyproject.toml"

        github_api.add("GET", url, UnknownObjectException(404, {"message": "No commit found for the ref nope"}, None))
        with pytest.raises(GithubException):
            self.repo.get_file_contents("pyproject.toml", branch="nope")

        github_api.add("GET", url, UnknownObjectException(404, {"message": "Not Found"}, None))
        with pytest.raises(FileNotFoundError):
            self.repo.get_file_contents("pyproject.toml", branch="nope")

    def test_set_status_without_description(self, github_api):
        self.repo.set_status("pending", None, None, "abc123", target_url="https://example.com")

        assert github_api.calls == [
            {
                "verb": "POST",
                "url": "https://api.github.com/repos/fakerepo/doesnotexist/statuses/abc123",
                "parameters": None,
                "input": {"state": "pending", "target_url": "https://example.com"},
            }
        ]


TEST_CONFIG = """
[tool.testbot]
[tool.testbot.pr]
setting1 = 2
setting2 = 3
"""


TEST_GLOBAL_CONFIG = """
[tool.testbot]
[tool.testbot.pr]
setting1 = 1
setting2 = 5
setting3 = 6
[tool.testbot.other]
setting4 = 5
"""


TEST_FALLBACK_CONFIG = """
[tool.nottestbot]
[tool.nottestbot.pr]
setting1 = 5
setting3 = 4
"""


@pytest.mark.github_api
class TestRealRepoHandler:
    def setup_method(self, method):
        FILE_CACHE.clear()

    def setup_class(self):
        self.repo = RepoHandler("OpenAstronomy/baldrick")

    def test_get_config(self, app):

        with app.app_context():
            with patch.object(self.repo, "get_file_contents") as mock_get:
                mock_get.return_value = TEST_CONFIG

                # These are set to False in YAML; defaults must not be used.
                assert self.repo.get_config_value("pr")["setting1"] == 2
                assert self.repo.get_config_value("pr")["setting2"] == 3

    def test_get_fallback_config(self, app):

        with app.app_context():
            app.fall_back_config = "nottestbot"
            with patch.object(self.repo, "get_file_contents") as mock_get:
                mock_get.return_value = TEST_FALLBACK_CONFIG

                # These are set to False in YAML; defaults must not be used.
                assert self.repo.get_config_value("pr")["setting1"] == 5
                assert self.repo.get_config_value("pr")["setting3"] == 4

    def test_get_fallback_with_primary_config(self, app):

        with app.app_context():
            app.fall_back_config = "nottestbot"
            with patch.object(self.repo, "get_file_contents") as mock_get:
                mock_get.return_value = TEST_CONFIG + TEST_FALLBACK_CONFIG

                # These are set to False in YAML; defaults must not be used.
                assert self.repo.get_config_value("pr")["setting1"] == 2
                assert self.repo.get_config_value("pr")["setting2"] == 3
                assert self.repo.get_config_value("pr")["setting3"] == 4

    def test_get_config_with_app_defaults(self, app):

        with app.app_context():
            with patch.object(self.repo, "get_file_contents") as mock_get:
                mock_get.return_value = TEST_CONFIG

                # These are set to False in YAML; defaults must not be used.
                assert self.repo.get_config_value("pr") == {"setting1": 2, "setting2": 3}
                assert self.repo.get_config_value("other") is None

                app.conf = loads(TEST_GLOBAL_CONFIG, tool="testbot")

                assert self.repo.get_config_value("pr") == {"setting1": 2, "setting2": 3, "setting3": 6}
                assert self.repo.get_config_value("other") == {"setting4": 5}

    def test_get_file_contents(self):
        result = self.repo.get_file_contents("README.rst", branch="main")
        assert "Baldrick" in result
        assert "cunning plan" in result

    def test_missing_file_contents(self):
        with pytest.raises(FileNotFoundError):
            self.repo.get_file_contents("this/file/does/not/exist.txt", branch="main")


class TestIssueHandler:
    def setup_class(self):
        self.issue = IssueHandler("fakerepo/doesnotexist", 1234)

    @pytest.mark.parametrize(("state", "answer"), [("open", False), ("closed", True)])
    def test_is_closed(self, state, answer):
        with patch("baldrick.github.github_api.IssueHandler.json", new_callable=PropertyMock) as mock_json:
            mock_json.return_value = {"state": state}
            assert self.issue.is_closed is answer

    def test_missing_labels(self):
        with patch("baldrick.github.github_api.IssueHandler.labels", new_callable=PropertyMock) as mock_issue_labels:
            mock_issue_labels.return_value = ["io.fits"]
            with patch("baldrick.github.github_api.RepoHandler.get_all_labels") as mock_repo_labels:
                mock_repo_labels.return_value = ["io.fits", "closed-by-bot"]

                # closed-by-bot label will be added to issue in POST
                missing_labels = self.issue._get_missing_labels("closed-by-bot")
                assert missing_labels == ["closed-by-bot"]

                # Desired labels do not exist in repo
                missing_labels = self.issue._get_missing_labels(["dummy", "foo"])
                assert missing_labels is None

                # Desired label already set on issue
                missing_labels = self.issue._get_missing_labels(["io.fits"])
                assert missing_labels is None

                # A mix
                missing_labels = self.issue._get_missing_labels(["io.fits", "closed-by-bot", "foo"])
                assert missing_labels == ["closed-by-bot"]

    def test_submit_comment_replace_with_string_id(self, github_api):
        github_api.add(
            "GET",
            "https://api.github.com/repos/fakerepo/doesnotexist/issues/1234",
            {"url": "https://api.github.com/repos/fakerepo/doesnotexist/issues/1234", "number": 1234},
        )

        self.issue.submit_comment("hello", comment_id="42")

        assert github_api.calls[-1] == {
            "verb": "PATCH",
            "url": "https://api.github.com/repos/fakerepo/doesnotexist/issues/comments/42",
            "parameters": None,
            "input": {"body": "hello"},
        }


class TestPullRequestHandler:
    def setup_class(self):
        self.pr = PullRequestHandler("fakerepo/doesnotexist", 1234)

    def test_has_modified(self, github_api):
        github_api.add(
            "GET",
            "https://api.github.com/repos/fakerepo/doesnotexist/pulls/1234",
            {"url": "https://api.github.com/repos/fakerepo/doesnotexist/pulls/1234", "number": 1234},
        )
        github_api.add(
            "GET",
            "https://api.github.com/repos/fakerepo/doesnotexist/pulls/1234/files",
            [
                {
                    "sha": "bbcd538c8e72b8c175046e27cc8f907076331401",
                    "filename": "file1.txt",
                    "status": "added",
                    "additions": 103,
                    "deletions": 21,
                    "changes": 124,
                    "blob_url": "https://github.com/blah/blah/blob/hash/file1.txt",
                    "raw_url": "https://github.com/blaht/blah/raw/hash/file1.txt",
                    "contents_url": "https://api.github.com/repos/blah/blah/contents/file1.txt?ref=hash",
                    "patch": "@@ -132,7 +132,7 @@ module Test @@ -1000,7 +1000,7 @@ module Test",
                }
            ],
        )

        assert self.pr.has_modified(["file1.txt"])
        assert self.pr.has_modified(["file1.txt", "notthis.txt"])
        assert not self.pr.has_modified(["notthis.txt"])

    def test_set_check(self, app, github_api):
        with patch("baldrick.github.github_api.PullRequestHandler.json", new_callable=PropertyMock) as json:
            json.return_value = {"head": {"sha": "987654321"}, "base": {"sha": "123456789"}}

            self.pr.set_check("baldrick-1", "hello", name="test")
            expected_json = {
                "external_id": "baldrick-1",
                "name": "test",
                "head_sha": "987654321",
                "status": "completed",
                "output": {"title": "hello", "summary": ""},
                "conclusion": "neutral",
            }
            assert github_api.calls[-1] == {
                "verb": "POST",
                "url": "https://api.github.com/repos/fakerepo/doesnotexist/check-runs",
                "parameters": None,
                "input": expected_json,
            }

            self.pr.set_check(
                "baldrick-1", "hello", name="test", commit_hash="base", text="hello world", summary="why hello"
            )
            expected_json = {
                "external_id": "baldrick-1",
                "name": "test",
                "head_sha": "123456789",
                "status": "completed",
                "output": {"title": "hello", "summary": "why hello", "text": "hello world"},
                "conclusion": "neutral",
            }
            assert github_api.calls[-1] == {
                "verb": "POST",
                "url": "https://api.github.com/repos/fakerepo/doesnotexist/check-runs",
                "parameters": None,
                "input": expected_json,
            }

            self.pr.set_check("baldrick-1", "hello", name="test", commit_hash="hello", details_url="this_is_a_url")
            expected_json = {
                "external_id": "baldrick-1",
                "name": "test",
                "head_sha": "hello",
                "details_url": "this_is_a_url",
                "status": "completed",
                "output": {"title": "hello", "summary": ""},
                "conclusion": "neutral",
            }
            assert github_api.calls[-1] == {
                "verb": "POST",
                "url": "https://api.github.com/repos/fakerepo/doesnotexist/check-runs",
                "parameters": None,
                "input": expected_json,
            }

            self.pr.set_check("baldrick-1", "hello", name="test", status="completed", conclusion=None)
            expected_json = {
                "external_id": "baldrick-1",
                "name": "test",
                "head_sha": "987654321",
                "status": "completed",
                "output": {"title": "hello", "summary": ""},
                "conclusion": "neutral",
            }
            assert github_api.calls[-1] == {
                "verb": "POST",
                "url": "https://api.github.com/repos/fakerepo/doesnotexist/check-runs",
                "parameters": None,
                "input": expected_json,
            }

    def test_submit_review_pins_commit(self, github_api):
        github_api.add(
            "GET",
            "https://api.github.com/repos/fakerepo/doesnotexist/pulls/1234",
            {"url": "https://api.github.com/repos/fakerepo/doesnotexist/pulls/1234", "number": 1234},
        )

        with patch("baldrick.github.github_api.PullRequestHandler.json", new_callable=PropertyMock) as json:
            json.return_value = {"head": {"sha": "987654321"}}
            self.pr.submit_review("approve", "Looks good")

        assert github_api.calls[-1] == {
            "verb": "POST",
            "url": "https://api.github.com/repos/fakerepo/doesnotexist/pulls/1234/reviews",
            "parameters": None,
            "input": {"body": "Looks good", "event": "APPROVE", "commit_id": "987654321", "comments": []},
        }

    def test_update_check(self, app, github_api):
        with patch("baldrick.github.github_api.PullRequestHandler.json", new_callable=PropertyMock) as json:
            json.return_value = {"head": {"sha": "987654321"}, "base": {"sha": "123456789"}}

            self.pr.set_check("baldrick-1", "hello", name="test", check_id=42)
            expected_json = {
                "external_id": "baldrick-1",
                "name": "test",
                "head_sha": "987654321",
                "status": "completed",
                "output": {"title": "hello", "summary": ""},
                "conclusion": "neutral",
            }
            assert github_api.calls[-1] == {
                "verb": "PATCH",
                "url": "https://api.github.com/repos/fakerepo/doesnotexist/check-runs/42",
                "parameters": None,
                "input": expected_json,
            }
