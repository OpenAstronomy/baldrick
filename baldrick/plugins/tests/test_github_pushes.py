import json
from copy import copy
from unittest.mock import MagicMock, patch

from baldrick.github.github_api import FILE_CACHE
from baldrick.plugins.github_pushes import PUSH_HANDLERS, push_handler

mock_handler = MagicMock()


CONFIG_TEMPLATE = """
[ tool.testbot ]
[ tool.testbot.pushes ]
enabled = true
"""


def setup_module(module):
    module.PUSH_HANDLERS_ORIG = copy(PUSH_HANDLERS)
    push_handler(mock_handler)


def teardown_module(module):
    PUSH_HANDLERS[:] = module.PUSH_HANDLERS_ORIG[:]


class TestPushHandler:
    def setup_method(self, method):

        mock_handler.reset_mock()

        # The ``app`` fixture (which runs after this method) patches the real
        # ``requests`` module globally, so patch the module as seen by
        # ``github_api`` only to avoid those patches shadowing these ones.
        self.requests_mock = patch("baldrick.github.github_api.requests")
        self.get_file_contents_mock = patch("baldrick.github.github_api.GitHubHandler.get_file_contents")
        self.get_installation_token_mock = patch("baldrick.github.github_auth.GithubAppAuth.get_installation_token")

        self.requests = self.requests_mock.start()
        self.get_file_contents = self.get_file_contents_mock.start()
        self.get_installation_token = self.get_installation_token_mock.start()

        self.requests.get.return_value.ok = True
        self.requests.get.return_value.json.return_value = {"default_branch": "main"}

        self.get_installation_token.return_value = "abcdefg"

        FILE_CACHE.clear()

    def teardown_method(self, method):
        self.requests_mock.stop()
        self.get_file_contents_mock.stop()
        self.get_installation_token_mock.stop()

    def send_event(self, client, github_webhook_headers, git_ref="refs/heads/main"):

        data = {"ref": git_ref, "repository": {"full_name": "test-repo"}, "installation": {"id": "123"}}
        headers = github_webhook_headers(data, {"X-GitHub-Event": "push"})

        client.post("/github", data=json.dumps(data), headers=headers, content_type="application/json")

    def test_branch(self, app, client, github_webhook_headers):
        self.get_file_contents.return_value = CONFIG_TEMPLATE
        self.send_event(client, github_webhook_headers, git_ref="refs/heads/experimental")
        assert mock_handler.call_count == 1
        repo_handler, git_ref = mock_handler.call_args[0]
        assert repo_handler.repo == "test-repo"
        assert repo_handler.branch == "experimental"
        assert git_ref == "refs/heads/experimental"

    def test_tags(self, app, client, github_webhook_headers):
        self.get_file_contents.return_value = CONFIG_TEMPLATE
        self.send_event(client, github_webhook_headers, git_ref="refs/tags/stable")
        assert mock_handler.call_count == 1
        repo_handler, git_ref = mock_handler.call_args[0]
        assert repo_handler.repo == "test-repo"
        assert repo_handler.branch is None
        assert git_ref == "refs/tags/stable"

    def test_disabled(self, app, client, github_webhook_headers):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.replace("enabled = true", "enabled = false")
        self.send_event(client, github_webhook_headers, git_ref="refs/tags/stable")
        assert mock_handler.call_count == 0

    def test_missing_config(self, app, client, github_webhook_headers):
        self.get_file_contents.return_value = ""
        self.send_event(client, github_webhook_headers, git_ref="refs/tags/stable")
        assert mock_handler.call_count == 0
