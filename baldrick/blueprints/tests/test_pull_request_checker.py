import json
from unittest.mock import patch

import pytest

from changebot.webapp import app


class TestHook:

    def setup_method(self, method):
        self.client = app.test_client()

    def test_valid(self):

        data = {'pull_request': {'number': '1234'},
                'repository': {'full_name': 'test-repo'},
                'action': 'synchronize',
                'installation': {'id': '123'}}

        headers = {'X-GitHub-Event': 'pull_request'}

        with patch('changebot.blueprints.pull_request_checker.process_changelog_consistency') as p:
            self.client.post('/hook', data=json.dumps(data), headers=headers,
                             content_type='application/json')
            p.assert_called_with('test-repo', '1234', '123')

    @pytest.mark.parametrize('state', ['open', 'closed'])
    def test_invalid(self, state):

        data = {'pull_request': {'number': '1234', 'state': state},
                'repository': {'full_name': 'test-repo'},
                'action': 'invalid_action',
                'installation': {'id': '123'}}

        headers = {'X-GitHub-Event': 'pull_request'}

        with patch('changebot.blueprints.pull_request_checker.process_changelog_consistency') as p:
            self.client.post('/hook', data=json.dumps(data), headers=headers,
                             content_type='application/json')
            assert p.call_count == 0
