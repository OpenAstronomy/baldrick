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


V1_PAYLOAD = {
    "vcs_revision": "2.0",
    "username": "test",
    "reponame": "testbot",
    "status": "passed",
    "build_num": "12356",
}

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

    def post_v1(self, client, payload, **kwargs):
        return client.post("/circleci", data=json.dumps(payload), content_type="application/json", **kwargs)

    def post_v2(self, client, payload, **kwargs):
        return client.post("/circleci/v2", data=json.dumps(payload), content_type="application/json", **kwargs)

    def test_valid(self, app, client):

        data = {"payload": V1_PAYLOAD}

        with patch("baldrick.blueprints.circleci.repo_to_installation_id_mapping") as mapping:
            mapping.return_value = {"test/testbot": 15554}
            result = self.post_v1(client, data)

        assert result.status_code == 200
        assert mock_hook.call_args[0][2]["vcs_revision"] == "2.0"

    def test_incorrect_repo(self, app, client):

        payload = dict(V1_PAYLOAD, reponame="testbot2")
        data = {"payload": payload}

        with patch("baldrick.blueprints.circleci.repo_to_installation_id_mapping") as mapping:
            mapping.return_value = {"test/testbot": 15554}
            result = self.post_v1(client, data)

        assert result.status_code == 200
        assert result.get_data() == b"circleci: Not installed for test/testbot2"

    def test_missing_payload_key(self, app, client):

        payload = {key: value for key, value in V1_PAYLOAD.items() if key != "reponame"}
        data = {"payload": payload}

        result = self.post_v1(client, data)

        assert result.status_code == 400
        assert result.get_data() == b"Payload missing reponame"

    def test_missing_payload(self, app, client):

        headers = {"X-GitHub-Event": "pull_request"}

        result = client.post("/circleci", headers=headers, content_type="application/json")

        assert result.status_code == 400
        assert result.get_data() == b"No payload received"

    def test_invalid_json(self, app, client):

        result = client.post("/circleci", data=b"{not valid json", content_type="application/json")

        assert result.status_code == 400
        assert result.get_data() == b"Payload is not valid JSON"

    def test_missing_payload_object(self, app, client):

        result = self.post_v1(client, V2_PAYLOAD)

        assert result.status_code == 400
        assert result.get_data() == b"Payload missing payload object"

    def test_installation_fetch_failure(self, app, client):

        data = {"payload": V1_PAYLOAD}

        with patch("baldrick.blueprints.circleci.repo_to_installation_id_mapping") as mapping:
            mapping.side_effect = ValueError("GitHub is down")
            result = self.post_v1(client, data)

        assert result.status_code == 502
        assert result.get_data() == b"Failed to fetch installations from GitHub"

    def test_handler_isolation(self, app, client):

        mock_hook.side_effect = ValueError("handler exploded")
        second_hook = MagicMock()
        CIRCLECI_WEBHOOK_HANDLERS.append(second_hook)
        data = {"payload": V1_PAYLOAD}
        try:
            with patch("baldrick.blueprints.circleci.repo_to_installation_id_mapping") as mapping:
                mapping.return_value = {"test/testbot": 15554}
                result = self.post_v1(client, data)
        finally:
            CIRCLECI_WEBHOOK_HANDLERS.remove(second_hook)
            mock_hook.side_effect = None

        assert result.status_code == 200
        assert second_hook.call_count == 1

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
