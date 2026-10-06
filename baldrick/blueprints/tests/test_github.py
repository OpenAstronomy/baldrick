import json
from copy import copy
from unittest.mock import MagicMock, patch

from baldrick.blueprints.github import GITHUB_WEBHOOK_HANDLERS, github_webhook_handler

mock_hook = MagicMock()


def setup_module(module):
    module.GITHUB_WEBOOK_HANDLERS_ORIGINAL = copy(GITHUB_WEBHOOK_HANDLERS)
    GITHUB_WEBHOOK_HANDLERS[:] = []
    github_webhook_handler(mock_hook)


def teardown_module(module):
    GITHUB_WEBHOOK_HANDLERS[:] = module.GITHUB_WEBOOK_HANDLERS_ORIGINAL[:]


class TestHook:
    def setup_method(self, method):
        mock_hook.reset_mock()

    def test_valid(self, app, client, github_webhook_headers):

        data = {
            "pull_request": {"number": "1234"},
            "repository": {"full_name": "test-repo"},
            "action": "synchronize",
            "installation": {"id": "123"},
        }

        headers = github_webhook_headers(data, {"X-GitHub-Event": "pull_request"})

        result = client.post("/github", data=json.dumps(data), headers=headers, content_type="application/json")

        assert result.status_code == 200
        assert mock_hook.call_args[0][1]["pull_request"]["number"] == "1234"
        assert mock_hook.call_args[0][1]["installation"]["id"] == "123"

    def test_missing_installation(self, app, client, github_webhook_headers):

        data = {"pull_request": {"number": "1234"}, "repository": {"full_name": "test-repo"}, "action": "synchronize"}

        headers = github_webhook_headers(data, {"X-GitHub-Event": "pull_request"})

        result = client.post("/github", data=json.dumps(data), headers=headers, content_type="application/json")

        assert result.status_code == 400
        assert result.get_data() == b"Payload missing installation or repository"

    def test_missing_payload(self, app, client, github_webhook_headers):

        headers = github_webhook_headers("", {"X-GitHub-Event": "pull_request"})

        result = client.post("/github", headers=headers, content_type="application/json")

        assert result.status_code == 400
        assert result.get_data() == b"No payload received"


class TestInstallationEvents:
    """Tests for installation and installation_repositories webhook dispatch."""

    def setup_method(self, method):
        mock_hook.reset_mock()

    def test_installation_created(self, app, client, github_webhook_headers):
        data = {"action": "created", "installation": {"id": 42}}

        with patch("baldrick.github.github_auth.add_installation") as mock_add, \
             patch("baldrick.github.github_auth.remove_installation") as mock_remove:
            headers = github_webhook_headers(data, {"X-GitHub-Event": "installation"})
            result = client.post("/github", data=json.dumps(data), headers=headers, content_type="application/json")

        assert result.status_code == 200
        mock_add.assert_called_once_with(42)
        mock_remove.assert_not_called()
        mock_hook.assert_not_called()

    def test_installation_deleted(self, app, client, github_webhook_headers):
        data = {"action": "deleted", "installation": {"id": 42}}

        with patch("baldrick.github.github_auth.add_installation") as mock_add, \
             patch("baldrick.github.github_auth.remove_installation") as mock_remove:
            headers = github_webhook_headers(data, {"X-GitHub-Event": "installation"})
            result = client.post("/github", data=json.dumps(data), headers=headers, content_type="application/json")

        assert result.status_code == 200
        mock_remove.assert_called_once_with(42)
        mock_add.assert_not_called()
        mock_hook.assert_not_called()

    def test_installation_suspended(self, app, client, github_webhook_headers):
        data = {"action": "suspended", "installation": {"id": 42}}

        with patch("baldrick.github.github_auth.remove_installation") as mock_remove:
            headers = github_webhook_headers(data, {"X-GitHub-Event": "installation"})
            result = client.post("/github", data=json.dumps(data), headers=headers, content_type="application/json")

        assert result.status_code == 200
        mock_remove.assert_called_once_with(42)

    def test_installation_unsuspended(self, app, client, github_webhook_headers):
        data = {"action": "unsuspended", "installation": {"id": 42}}

        with patch("baldrick.github.github_auth.add_installation") as mock_add:
            headers = github_webhook_headers(data, {"X-GitHub-Event": "installation"})
            result = client.post("/github", data=json.dumps(data), headers=headers, content_type="application/json")

        assert result.status_code == 200
        mock_add.assert_called_once_with(42)

    def test_installation_new_permissions_accepted_noop(self, app, client, github_webhook_headers):
        data = {"action": "new_permissions_accepted", "installation": {"id": 42}}

        with patch("baldrick.github.github_auth.add_installation") as mock_add, \
             patch("baldrick.github.github_auth.remove_installation") as mock_remove:
            headers = github_webhook_headers(data, {"X-GitHub-Event": "installation"})
            result = client.post("/github", data=json.dumps(data), headers=headers, content_type="application/json")

        assert result.status_code == 200
        mock_add.assert_not_called()
        mock_remove.assert_not_called()

    def test_installation_repositories_added(self, app, client, github_webhook_headers):
        data = {
            "action": "added",
            "installation": {"id": 42},
            "repositories_added": [
                {"full_name": "foo/bar"},
                {"full_name": "baz/qux"},
            ],
        }

        with patch("baldrick.github.github_auth.add_repositories_to_installation") as mock_add, \
             patch("baldrick.github.github_auth.remove_repositories_from_installation") as mock_remove:
            headers = github_webhook_headers(data, {"X-GitHub-Event": "installation_repositories"})
            result = client.post("/github", data=json.dumps(data), headers=headers, content_type="application/json")

        assert result.status_code == 200
        mock_add.assert_called_once_with(42, ["foo/bar", "baz/qux"])
        mock_remove.assert_not_called()
        mock_hook.assert_not_called()

    def test_installation_repositories_removed(self, app, client, github_webhook_headers):
        data = {
            "action": "removed",
            "installation": {"id": 42},
            "repositories_removed": [
                {"full_name": "foo/bar"},
            ],
        }

        with patch("baldrick.github.github_auth.add_repositories_to_installation") as mock_add, \
             patch("baldrick.github.github_auth.remove_repositories_from_installation") as mock_remove:
            headers = github_webhook_headers(data, {"X-GitHub-Event": "installation_repositories"})
            result = client.post("/github", data=json.dumps(data), headers=headers, content_type="application/json")

        assert result.status_code == 200
        mock_remove.assert_called_once_with(["foo/bar"])
        mock_add.assert_not_called()
        mock_hook.assert_not_called()

    def test_installation_handler_error_returns_502(self, app, client, github_webhook_headers):
        data = {"action": "created", "installation": {"id": 42}}

        with patch("baldrick.github.github_auth.add_installation", side_effect=RuntimeError("boom")):
            headers = github_webhook_headers(data, {"X-GitHub-Event": "installation"})
            result = client.post("/github", data=json.dumps(data), headers=headers, content_type="application/json")

        assert result.status_code == 502
        mock_hook.assert_not_called()
