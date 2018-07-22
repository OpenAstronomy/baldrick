import json
from copy import copy
from unittest.mock import MagicMock, patch

from baldrick.blueprints.circleci import circleci_webhook_handler, CIRCLECI_WEBHOOK_HANDLERS

test_hook = MagicMock()


def setup_module(module):
    module.CIRCLECI_WEBOOK_HANDLERS_ORIGINAL = copy(CIRCLECI_WEBHOOK_HANDLERS)
    circleci_webhook_handler(test_hook)


def teardown_module(module):
    CIRCLECI_WEBHOOK_HANDLERS[:] = module.CIRCLECI_WEBOOK_HANDLERS_ORIGINAL[:]


class TestHook:

    def setup_method(self, method):
        test_hook.resetmock()

    def test_valid(self, app, client):

        payload = {'vcs_revision': '2.0',
                   'username': 'test',
                   'reponame': 'testbot',
                   'status': 'passed',
                   'build_num': '12356'}

        data = {'payload': payload}

        with patch('baldrick.blueprints.circleci.repo_to_installationid_mapping') as mapping:
            mapping.return_value = {'test/testbot': 15554}
            client.post('/circleci', data=json.dumps(data),
                        content_type='application/json')

        assert test_hook.call_args[0][1]['vcs_revision'] == '2.0'

    def test_incorrect_repo(self, app, client):

        payload = {'vcs_revision': '2.0',
                   'username': 'test',
                   'reponame': 'testbot2',
                   'status': 'passed',
                   'build_num': '12356'}

        data = {'payload': payload}

        with patch('baldrick.blueprints.circleci.repo_to_installationid_mapping') as mapping:
            mapping.return_value = {'test/testbot': 15554}
            result = client.post('/circleci', data=json.dumps(data),
                                 content_type='application/json')

        assert result.get_data() == b'circleci: Not installed for test/testbot2'

    def test_missing_payload_key(self, app, client):

        payload = {'vcs_revision': '2.0',
                   'username': 'test',
                   'status': 'passed',
                   'build_num': '12356'}

        data = {'payload': payload}

        result = client.post('/circleci', data=json.dumps(data),
                             content_type='application/json')

        assert result.get_data() == b'Payload missing reponame'

    def test_missing_payload(self, app, client):

        headers = {'X-GitHub-Event': 'pull_request'}

        result = client.post('/circleci', headers=headers,
                             content_type='application/json')

        assert result.get_data() == b'No payload received'
