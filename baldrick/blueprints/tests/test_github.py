import json
from copy import copy
from unittest.mock import MagicMock

import pytest

from baldrick.blueprints.github import GITHUB_WEBHOOK_HANDLERS, github_webhook_handler
from baldrick.github.github_auth import GithubAppAuth

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


@pytest.fixture(autouse=True)
def reset_mock_hook():
    mock_hook.reset_mock()


@pytest.fixture
def post_webhook(client, github_webhook_headers):
    def post(payload, event, signed=True):
        headers = {"X-GitHub-Event": event}
        if signed:
            headers = github_webhook_headers(payload, headers)
        return client.post("/github", data=json.dumps(payload), headers=headers, content_type="application/json")

    return post


def test_installation_created(post_webhook, mocker):
    add_installation = mocker.patch.object(GithubAppAuth, "add_installation")

    result = post_webhook({"action": "created", "installation": {"id": 12345}}, "installation")

    assert result.status_code == 200
    add_installation.assert_called_once_with(12345)
    assert mock_hook.call_count == 0


def test_installation_deleted(post_webhook, mocker):
    remove_installation = mocker.patch.object(GithubAppAuth, "remove_installation")

    result = post_webhook({"action": "deleted", "installation": {"id": 12345}}, "installation")

    assert result.status_code == 200
    remove_installation.assert_called_once_with(12345)
    assert mock_hook.call_count == 0


def test_installation_suspended(post_webhook, mocker):
    remove_installation = mocker.patch.object(GithubAppAuth, "remove_installation")

    result = post_webhook({"action": "suspended", "installation": {"id": 12345}}, "installation")

    assert result.status_code == 200
    remove_installation.assert_called_once_with(12345)


def test_installation_unsuspended(post_webhook, mocker):
    add_installation = mocker.patch.object(GithubAppAuth, "add_installation")

    result = post_webhook({"action": "unsuspended", "installation": {"id": 12345}}, "installation")

    assert result.status_code == 200
    add_installation.assert_called_once_with(12345)


def test_installation_unhandled_action(post_webhook, mocker):
    add_installation = mocker.patch.object(GithubAppAuth, "add_installation")
    remove_installation = mocker.patch.object(GithubAppAuth, "remove_installation")

    result = post_webhook({"action": "new_permissions_accepted", "installation": {"id": 12345}}, "installation")

    assert result.status_code == 200
    add_installation.assert_not_called()
    remove_installation.assert_not_called()
    assert mock_hook.call_count == 0


def test_installation_repositories_added(post_webhook, mocker):
    add_repositories = mocker.patch.object(GithubAppAuth, "add_repositories_to_installation")

    payload = {
        "action": "added",
        "installation": {"id": 12345},
        "repositories_added": [{"full_name": "test-repo"}],
        "repositories_removed": [],
    }
    result = post_webhook(payload, "installation_repositories")

    assert result.status_code == 200
    add_repositories.assert_called_once_with(12345, ["test-repo"])
    assert mock_hook.call_count == 0


def test_installation_repositories_removed(post_webhook, mocker):
    remove_repositories = mocker.patch.object(GithubAppAuth, "remove_repositories_from_installation")

    payload = {
        "action": "removed",
        "installation": {"id": 12345},
        "repositories_added": [],
        "repositories_removed": [{"full_name": "test-repo"}],
    }
    result = post_webhook(payload, "installation_repositories")

    assert result.status_code == 200
    remove_repositories.assert_called_once_with(["test-repo"])
    assert mock_hook.call_count == 0


def test_installation_update_failure(post_webhook, mocker):
    add_installation = mocker.patch.object(GithubAppAuth, "add_installation", side_effect=ValueError("GitHub is down"))

    result = post_webhook({"action": "created", "installation": {"id": 12345}}, "installation")

    assert result.status_code == 502
    assert mock_hook.call_count == 0


def test_installation_event_rejected_without_signature(post_webhook):
    result = post_webhook({"action": "created", "installation": {"id": 12345}}, "installation", signed=False)

    assert result.status_code == 403
    assert result.get_data() == b"Invalid or missing webhook signature"
    assert mock_hook.call_count == 0
