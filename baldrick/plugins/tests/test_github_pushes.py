import json
from copy import copy
from unittest.mock import MagicMock, patch

from baldrick.github.github_api import FILE_CACHE
from baldrick.plugins.github_pushes import push_handler, PUSH_HANDLERS

test_handler = MagicMock()


CONFIG_TEMPLATE = """
[ tool.testbot ]
[ tool.testbot.pushes ]
enabled = true
"""


def setup_module(module):
    module.PUSH_HANDLERS_ORIG = copy(PUSH_HANDLERS)
    push_handler(test_handler)


def teardown_module(module):
    PUSH_HANDLERS[:] = module.PUSH_HANDLERS_ORIG[:]


class TestPushHandler:

    def setup_method(self, method):

        test_handler.reset_mock()

        self.get_file_contents_mock = patch('baldrick.github.github_api.GitHubHandler.get_file_contents')
        self.get_installation_token_mock = patch('baldrick.github.github_auth.get_installation_token')

        self.get_file_contents = self.get_file_contents_mock.start()
        self.get_installation_token = self.get_installation_token_mock.start()

        self.get_installation_token.return_value = 'abcdefg'

        FILE_CACHE.clear()

    def teardown_method(self, method):
        self.get_file_contents_mock.stop()
        self.get_installation_token_mock.stop()

    def send_event(self, client, git_ref='refs/heads/master'):

        data = {'ref': git_ref,
                'repository': {'full_name': 'test-repo'},
                'installation': {'id': '123'}}
        headers = {'X-GitHub-Event': 'push'}

        client.post('/github', data=json.dumps(data), headers=headers,
                    content_type='application/json')

    def test_branch(self, app, client):
        self.get_file_contents.return_value = CONFIG_TEMPLATE
        self.send_event(client, git_ref='refs/heads/experimental')
        assert test_handler.call_count == 1
        repo_handler, git_ref = test_handler.call_args[0]
        assert repo_handler.repo == 'test-repo'
        assert repo_handler.branch == 'experimental'
        assert git_ref == 'refs/heads/experimental'

    def test_tags(self, app, client):
        self.get_file_contents.return_value = CONFIG_TEMPLATE
        self.send_event(client, git_ref='refs/tags/stable')
        assert test_handler.call_count == 1
        repo_handler, git_ref = test_handler.call_args[0]
        assert repo_handler.repo == 'test-repo'
        assert repo_handler.branch == 'master'
        assert git_ref == 'refs/tags/stable'

    def test_disabled(self, app, client):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.replace('enabled = true',
                                                                      'enabled = false')
        self.send_event(client, git_ref='refs/tags/stable')
        assert test_handler.call_count == 0

    def test_missing_config(self, app, client):
        self.get_file_contents.return_value = ""
        self.send_event(client, git_ref='refs/tags/stable')
        assert test_handler.call_count == 0
