import hashlib
import hmac
import json
import os
from copy import copy
from unittest.mock import MagicMock, patch

import pytest

from baldrick import create_app
from baldrick.blueprints.github import GITHUB_WEBHOOK_HANDLERS, github_webhook_handler
from baldrick.conftest import PRIVATE_KEY, WEBHOOK_SECRET
from baldrick.webhooks import verify_github_signature

mock_first = MagicMock()
mock_second = MagicMock()


def setup_module(module):
    module.GITHUB_WEBOOK_HANDLERS_ORIGINAL = copy(GITHUB_WEBHOOK_HANDLERS)
    GITHUB_WEBHOOK_HANDLERS[:] = []
    github_webhook_handler(mock_first)
    github_webhook_handler(mock_second)


def teardown_module(module):
    GITHUB_WEBHOOK_HANDLERS[:] = module.GITHUB_WEBOOK_HANDLERS_ORIGINAL[:]


def sign(payload, secret=WEBHOOK_SECRET):
    if isinstance(payload, str):
        body = payload.encode("utf-8")
    elif isinstance(payload, (bytes, bytearray)):
        body = bytes(payload)
    else:
        body = json.dumps(payload).encode("utf-8")
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


VALID_PAYLOAD = {
    "pull_request": {"number": "1234"},
    "repository": {"full_name": "test-repo"},
    "action": "synchronize",
    "installation": {"id": "123"},
}


class TestVerifyGithubSignature:
    def test_valid_signature(self):
        body = b'{"hello": "world"}'
        assert verify_github_signature(body, sign(body), WEBHOOK_SECRET)

    def test_signature_from_wrong_secret(self):
        body = b'{"hello": "world"}'
        assert not verify_github_signature(body, sign(body, "wrong-secret"), WEBHOOK_SECRET)

    def test_signature_over_wrong_payload(self):
        assert not verify_github_signature(b'{"tampered": true}', sign(b'{"hello": "world"}'), WEBHOOK_SECRET)

    def test_missing_signature(self):
        assert not verify_github_signature(b'{"hello": "world"}', None, WEBHOOK_SECRET)

    def test_wrong_algorithm_prefix(self):
        body = b'{"hello": "world"}'
        digest = hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
        assert not verify_github_signature(body, "sha1=" + digest, WEBHOOK_SECRET)

    def test_non_ascii_signature(self):
        assert not verify_github_signature(b'{"hello": "world"}', "sha256=éééé", WEBHOOK_SECRET)

    def test_empty_secret(self):
        assert not verify_github_signature(b'{"hello": "world"}', sign(b'{"hello": "world"}'), "")


class TestWebhookSignatureEnforcement:
    def setup_method(self, method):
        mock_first.reset_mock(side_effect=True)
        mock_second.reset_mock(side_effect=True)

    def post(self, client, payload, headers=None, sign_payload=True):
        body = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
        all_headers = dict(headers or {})
        if sign_payload and "X-Hub-Signature-256" not in all_headers:
            all_headers["X-Hub-Signature-256"] = sign(payload)
        return client.post("/github", data=body, headers=all_headers, content_type="application/json")

    def test_unsigned_webhook_rejected(self, app, client):
        result = self.post(client, VALID_PAYLOAD, sign_payload=False)

        assert result.status_code == 403
        assert result.get_data() == b"Invalid or missing webhook signature"
        assert mock_first.call_count == 0
        assert mock_second.call_count == 0

    def test_bad_signature_rejected(self, app, client):
        result = self.post(client, VALID_PAYLOAD, headers={"X-Hub-Signature-256": "sha256=" + "0" * 64})

        assert result.status_code == 403
        assert mock_first.call_count == 0

    def test_tampered_payload_rejected(self, app, client):
        headers = {"X-Hub-Signature-256": sign({"something": "else"})}
        result = self.post(client, VALID_PAYLOAD, headers=headers, sign_payload=False)

        assert result.status_code == 403
        assert mock_first.call_count == 0

    def test_signed_webhook_accepted(self, app, client):
        result = self.post(client, VALID_PAYLOAD, headers={"X-GitHub-Event": "pull_request"})

        assert result.status_code == 200
        assert result.get_data() == b"GitHub Webhook Finished"
        assert mock_first.call_args[0][1] == VALID_PAYLOAD
        assert mock_second.call_args[0][1] == VALID_PAYLOAD

    def test_malformed_json_rejected(self, app, client):
        result = self.post(client, b"{not valid json")

        assert result.status_code == 400
        assert result.get_data() == b"Payload is not valid JSON"
        assert mock_first.call_count == 0

    def test_non_object_payload_rejected(self, app, client):
        result = self.post(client, [1, 2, 3])

        assert result.status_code == 400
        assert result.get_data() == b"Payload is not a JSON object"
        assert mock_first.call_count == 0

    def test_missing_repository_rejected(self, app, client):
        payload = {"pull_request": {"number": "1234"}, "action": "synchronize", "installation": {"id": "123"}}
        result = self.post(client, payload, headers={"X-GitHub-Event": "pull_request"})

        assert result.status_code == 400
        assert result.get_data() == b"Payload missing installation or repository"
        assert mock_first.call_count == 0

    def test_ping_event_ignored(self, app, client):
        payload = {"zen": "Keep it logically awesome.", "hook_id": 42}
        result = self.post(client, payload, headers={"X-GitHub-Event": "ping"})

        assert result.status_code == 200
        assert result.get_data() == b"Ping received"
        assert mock_first.call_count == 0

    def test_handler_failure_does_not_block_other_handlers(self, app, client):
        mock_first.side_effect = ValueError("handler exploded")

        result = self.post(client, VALID_PAYLOAD, headers={"X-GitHub-Event": "pull_request"})

        assert result.status_code == 200
        assert mock_second.call_count == 1

    def test_unverified_webhooks_allowed_with_escape_hatch(self):
        env = {
            "GITHUB_APP_INTEGRATION_ID": "1234",
            "GITHUB_APP_PRIVATE_KEY": PRIVATE_KEY,
            "GITHUB_APP_WEBHOOK_SECRET": "",
            "BALDRICK_ALLOW_UNVERIFIED_WEBHOOKS": "1",
        }
        with patch.dict(os.environ, env):
            with patch("baldrick.github.github_auth.repo_to_installation_id_mapping") as mock_mapping:
                mock_mapping.return_value = {"test/test-repo": 123}
                app = create_app("testbot")
        client = app.test_client()

        result = self.post(client, VALID_PAYLOAD, sign_payload=False)

        assert result.status_code == 200
        assert mock_first.call_count == 1


class TestStartupValidation:
    BASE_ENV = {
        "GITHUB_APP_INTEGRATION_ID": "1234",
        "GITHUB_APP_PRIVATE_KEY": PRIVATE_KEY,
        "GITHUB_APP_WEBHOOK_SECRET": WEBHOOK_SECRET,
        "BALDRICK_ALLOW_UNVERIFIED_WEBHOOKS": "",
    }

    def create_app_with_env(self, env):
        with patch.dict(os.environ, env):
            return create_app("testbot")

    def test_missing_webhook_secret(self):
        env = dict(self.BASE_ENV, GITHUB_APP_WEBHOOK_SECRET="")
        with pytest.raises(RuntimeError, match="GITHUB_APP_WEBHOOK_SECRET is not set"):
            self.create_app_with_env(env)

    def test_missing_integration_id(self):
        env = dict(self.BASE_ENV, GITHUB_APP_INTEGRATION_ID="")
        with pytest.raises(RuntimeError, match="GITHUB_APP_INTEGRATION_ID is not set"):
            self.create_app_with_env(env)

    def test_invalid_integration_id(self):
        env = dict(self.BASE_ENV, GITHUB_APP_INTEGRATION_ID="not-an-int")
        with pytest.raises(RuntimeError, match="must be an integer"):
            self.create_app_with_env(env)

    def test_missing_private_key(self):
        env = dict(self.BASE_ENV, GITHUB_APP_PRIVATE_KEY="")
        with pytest.raises(RuntimeError, match="GITHUB_APP_PRIVATE_KEY is not set"):
            self.create_app_with_env(env)

    def test_auth_failure_raises_at_startup(self):
        with patch.dict(os.environ, self.BASE_ENV):
            with patch("baldrick.github.github_auth.repo_to_installation_id_mapping") as mock_mapping:
                mock_mapping.side_effect = ValueError("GitHub is down")
                with pytest.raises(ValueError, match="GitHub is down"):
                    create_app("testbot")

    def test_valid_environment_starts(self):
        with patch.dict(os.environ, self.BASE_ENV):
            with patch("baldrick.github.github_auth.repo_to_installation_id_mapping") as mock_mapping:
                mock_mapping.return_value = {"test/test-repo": 123}
                app = create_app("testbot")
        assert app.webhook_secret == WEBHOOK_SECRET
        assert app.allow_unverified_webhooks is False
