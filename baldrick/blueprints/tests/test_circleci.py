import json
from copy import copy
from unittest.mock import MagicMock, patch

from baldrick.blueprints.circleci import CIRCLECI_WEBHOOK_HANDLERS, circleci_webhook_handler

mock_hook = MagicMock()


def setup_module(module):
    module.CIRCLECI_WEBOOK_HANDLERS_ORIGINAL = copy(CIRCLECI_WEBHOOK_HANDLERS)
    CIRCLECI_WEBHOOK_HANDLERS[:] = []
    circleci_webhook_handler(mock_hook)


def teardown_module(module):
    CIRCLECI_WEBHOOK_HANDLERS[:] = module.CIRCLECI_WEBOOK_HANDLERS_ORIGINAL[:]

V2_PAYLOAD = {
    "job": {"status": "passed", "number": 42},
    "pipeline": {
        "vcs": {
            "provider_name": "github",
            "target_repository_url": "https://github.com/test/testbot",
            "branch": "main",
            "revision": "abc123",
        }
    },
}


class TestHook:
    def setup_method(self, method):
        mock_hook.reset_mock()

    def post_v2(self, client, payload, **kwargs):
        return client.post("/circleci/v2", data=json.dumps(payload), content_type="application/json", **kwargs)

    def test_valid_v2(self, app, client):

        with patch("baldrick.blueprints.circleci.repo_to_installation_id_mapping") as mapping:
            mapping.return_value = {"test/testbot": 15554}
            result = self.post_v2(client, V2_PAYLOAD)

        assert result.status_code == 200
        repo_handler, version, _payload, _headers, status, revision, build_num = mock_hook.call_args[0]
        assert version == "v2"
        assert status == "passed"
        assert revision == "abc123"
        assert build_num == 42
        assert repo_handler.repo == "test/testbot"

    def test_v2_missing_objects(self, app, client):

        result = self.post_v2(client, {"job": {"status": "passed"}})

        assert result.status_code == 400
        assert result.get_data() == b"Payload missing pipeline"

    def test_v2_not_github(self, app, client):

        payload = {
            "job": {"status": "passed", "number": 42},
            "pipeline": {
                "vcs": {
                    "provider_name": "bitbucket",
                    "target_repository_url": "https://bitbucket.org/test/testbot",
                    "revision": "abc123",
                }
            },
        }

        result = self.post_v2(client, payload)

        assert result.status_code == 200
        assert result.get_data() == b"Only GitHub repositories are supported."
        assert mock_hook.call_count == 0

    def test_v2_not_installed(self, app, client):

        with patch("baldrick.blueprints.circleci.repo_to_installation_id_mapping") as mapping:
            mapping.return_value = {"other/repo": 15554}
            result = self.post_v2(client, V2_PAYLOAD)

        assert result.status_code == 200
        assert result.get_data() == b"Not installed for test/testbot"
        assert mock_hook.call_count == 0

    def test_v2_installation_fetch_failure(self, app, client):

        with patch("baldrick.blueprints.circleci.repo_to_installation_id_mapping") as mapping:
            mapping.side_effect = ValueError("GitHub is down")
            result = self.post_v2(client, V2_PAYLOAD)

        assert result.status_code == 502
        assert result.get_data() == b"Failed to fetch installations from GitHub"
        assert mock_hook.call_count == 0

    def test_v2_handler_isolation(self, app, client):

        mock_hook.side_effect = ValueError("handler exploded")
        second_hook = MagicMock()
        CIRCLECI_WEBHOOK_HANDLERS.append(second_hook)
        try:
            with patch("baldrick.blueprints.circleci.repo_to_installation_id_mapping") as mapping:
                mapping.return_value = {"test/testbot": 15554}
                result = self.post_v2(client, V2_PAYLOAD)
        finally:
            CIRCLECI_WEBHOOK_HANDLERS.remove(second_hook)
            mock_hook.side_effect = None

        assert result.status_code == 200
        assert second_hook.call_count == 1
