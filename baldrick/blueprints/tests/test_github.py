import os
import json
from copy import copy
from unittest.mock import MagicMock

from baldrick import create_app
from baldrick.blueprints.github import github_webhook_handler, GITHUB_WEBHOOK_HANDLERS


test_hook = MagicMock()


def setup_module(module):
    module.GITHUB_WEBOOK_HANDLERS_ORIGINAL = copy(GITHUB_WEBHOOK_HANDLERS)
    github_webhook_handler(test_hook)


def teardown_module(module):
    GITHUB_WEBHOOK_HANDLERS[:] = module.GITHUB_WEBOOK_HANDLERS_ORIGINAL[:]


class TestHook:

    def setup_class(self):
        os.environ['GITHUB_APP_INTEGRATION_ID'] = '22223'
        os.environ['GITHUB_APP_PRIVATE_KEY'] = 'ABCD'
        self.app = create_app('testbot')

    def setup_method(self, method):
        self.client = self.app.test_client()
        test_hook.resetmock()

    def test_valid(self):

        data = {'pull_request': {'number': '1234'},
                'repository': {'full_name': 'test-repo'},
                'action': 'synchronize',
                'installation': {'id': '123'}}

        headers = {'X-GitHub-Event': 'pull_request'}

        self.client.post('/github', data=json.dumps(data), headers=headers,
                         content_type='application/json')

        assert test_hook.call_args[0][1]['pull_request']['number'] == '1234'
        assert test_hook.call_args[0][1]['installation']['id'] == '123'

    def test_missing_installation(self):

        data = {'pull_request': {'number': '1234'},
                'repository': {'full_name': 'test-repo'},
                'action': 'synchronize'}

        headers = {'X-GitHub-Event': 'pull_request'}

        result = self.client.post('/github', data=json.dumps(data), headers=headers,
                                  content_type='application/json')

        assert result.get_data() == b'No installation key found in payload'

    def test_missing_payload(self):

        headers = {'X-GitHub-Event': 'pull_request'}

        result = self.client.post('/github', headers=headers,
                                  content_type='application/json')

        assert result.get_data() == b'No payload received'
