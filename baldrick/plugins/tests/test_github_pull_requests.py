import json
from copy import copy
from unittest.mock import MagicMock, patch

from baldrick.plugins.github_pull_requests import pull_request_handler, PULL_REQUEST_CHECKS

TEST_CONFIG = """
[tool.testbot]
[tool.testbot.pull_requests]
post_pr_comment = true
all_passed_message = ''
"""

test_hook = MagicMock()

def setup_module(module):
    module.PULL_REQUEST_CHECKS_ORIG = copy(PULL_REQUEST_CHECKS)
    pull_request_handler(test_hook)


def teardown_module(module):
    PULL_REQUEST_CHECKS[:] = module.PULL_REQUEST_CHECKS_ORIG[:]


class TestPullRequestHandler:

    def setup_method(self, method):
        test_hook.resetmock()

    def test_valid(self, app, client):

        data = {'pull_request': {'number': '1234'},
                'repository': {'full_name': 'test-repo'},
                'action': 'synchronize',
                'installation': {'id': '123'}}

        headers = {'X-GitHub-Event': 'pull_request'}

        def request_get_patched(url, headers=None):
            req = MagicMock()
            req.ok = True
            if url == 'https://api.github.com/repos/test-repo/pulls/1234':
                req.json.return_value = {'base': {'ref': 'master'},
                                         'state': 'open',
                                         'head': {'ref': 'custom', 'sha': 'abc464aa',
                                                  'repo': {'full_name': 'contributor/test'}}}
                return req
            elif url == 'https://api.github.com/repos/test-repo/issues/1234/comments':
                req.json.return_value = []
            else:
                raise ValueError('Unexepected URL: {0}'.format(url))
            return req

        test_hook.return_value = [], True

        with patch('requests.get', request_get_patched):
            with patch('requests.post') as request_post_patched:
                with patch('baldrick.github.github_api.GitHubHandler.get_file_contents') as get_file:  # noqa
                    get_file.return_value = TEST_CONFIG
                    with patch('baldrick.github.github_auth.get_installation_token') as get_token:
                        get_token.return_value = 'abcdefg'
                        client.post('/github', data=json.dumps(data), headers=headers,
                                    content_type='application/json')

        args, kwargs = request_post_patched.call_args
        assert args[0] == 'https://api.github.com/repos/test-repo/statuses/abc464aa'
        assert kwargs['json'] == {'state': 'success',
                                  'description': 'Passed all checks',
                                  'context': 'testbot'}
