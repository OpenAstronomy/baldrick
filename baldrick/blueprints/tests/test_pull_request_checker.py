import json
from unittest.mock import patch, PropertyMock

import pytest

from baldrick.webapp import app
from baldrick.github.github_api import RepoHandler, PullRequestHandler
from baldrick.blueprints.pull_request_checker import (
    process_changelog_consistency, CHANGELOG_PROLOGUE, CHANGELOG_NOT_DONE,
    CHANGELOG_BAD_LIST, CHANGELOG_BAD_EPILOGUE, CHANGELOG_GOOD,
    CHANGELOG_EPILOGUE)


class TestHook:

    def setup_method(self, method):
        self.client = app.test_client()

    def test_valid(self):

        data = {'pull_request': {'number': '1234'},
                'repository': {'full_name': 'test-repo'},
                'action': 'synchronize',
                'installation': {'id': '123'}}

        headers = {'X-GitHub-Event': 'pull_request'}

        with patch('baldrick.blueprints.pull_request_checker.process_changelog_consistency') as p:
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

        with patch('baldrick.blueprints.pull_request_checker.process_changelog_consistency') as p:
            self.client.post('/hook', data=json.dumps(data), headers=headers,
                             content_type='application/json')
            assert p.call_count == 0


class TestProcessChangelog:

    def setup_method(self, method):

        # Closed PR already tested in TestHook.test_invalid()
        pr_json = {'state': 'open',
                   'user': {'login': 'user'},
                   'head': {'repo': {'full_name': 'repo'},
                            'ref': 'branch'}}

        self.patch_repo_config = patch.object(RepoHandler, 'get_config_value')
        self.patch_pr_json = patch.object(
            PullRequestHandler, 'json', new_callable=PropertyMock,
            return_value=pr_json)
        self.patch_pr_comments = patch.object(
            PullRequestHandler, 'find_comments', return_value=[])
        self.patch_pr_labels = patch.object(
            PullRequestHandler, 'labels', new_callable=PropertyMock)
        self.patch_submit_comment = patch.object(
            PullRequestHandler, 'submit_comment', return_value='url')
        self.patch_set_status = patch.object(PullRequestHandler, 'set_status')
        self.patch_check_changelog = patch('baldrick.blueprints.pull_request_checker.check_changelog_consistency')

        self.changelog_cfg = self.patch_repo_config.start()
        self.patch_pr_json.start()
        self.comment_ids = self.patch_pr_comments.start()
        self.labels = self.patch_pr_labels.start()
        self.submit_comment = self.patch_submit_comment.start()
        self.set_status = self.patch_set_status.start()
        self.issues = self.patch_check_changelog.start()

    def teardown_method(self, method):

        self.patch_repo_config.stop()
        self.patch_pr_json.stop()
        self.patch_pr_comments.stop()
        self.patch_pr_labels.stop()
        self.patch_submit_comment.stop()
        self.patch_set_status.stop()
        self.patch_check_changelog.stop()

    def test_config_noop(self):

        # Repo does not want any changelog check.

        self.changelog_cfg.return_value = False

        with app.app_context():
            process_changelog_consistency('repo', '1234', 'installation')

        assert self.issues.call_count == 0

    def test_good(self):

        # Change log has no issue.

        self.changelog_cfg.return_value = True
        self.labels.return_value = []
        self.issues.return_value = []
        self.comment_ids.return_value = ['123', '456']
        expected = (CHANGELOG_PROLOGUE.format(user='user') + CHANGELOG_GOOD +
                    CHANGELOG_EPILOGUE)

        with app.app_context():
            process_changelog_consistency('repo', '1234', 'installation')

        assert self.issues.call_count == 1
        self.submit_comment.assert_called_with(
            expected, comment_id='456', return_url=True)
        self.set_status.assert_called_with(
            'success', 'All checks passed', 'astropy-bot', target_url='url')

    def test_bad_1(self):

        # Change log has 1 issue.

        self.changelog_cfg.return_value = True
        self.labels.return_value = []
        self.issues.return_value = ['One issue']
        self.comment_ids.return_value = ['123']
        expected = (CHANGELOG_PROLOGUE.format(user='user') +
                    CHANGELOG_BAD_LIST +
                    '* {0}\n'.format('One issue') +
                    CHANGELOG_BAD_EPILOGUE)
        expected = (expected.replace('issues with', 'issue with')
                    .replace('fix these', 'fix this'))
        expected += CHANGELOG_EPILOGUE

        with app.app_context():
            process_changelog_consistency('repo', '1234', 'installation')

        assert self.issues.call_count == 1
        self.submit_comment.assert_called_with(
            expected, comment_id='123', return_url=True)
        self.set_status.assert_called_with(
            'failure', 'There were failures in checks - see '
            'comments by @astropy-bot above', 'astropy-bot', target_url='url')

    def test_bad_2(self):

        # Change log has multiple issues.

        self.changelog_cfg.return_value = True
        self.labels.return_value = []
        self.issues.return_value = ['One issue', 'OMG another one']
        self.comment_ids.return_value = []
        expected = (CHANGELOG_PROLOGUE.format(user='user') +
                    CHANGELOG_BAD_LIST +
                    '* {0}\n'.format('One issue') +
                    '* {0}\n'.format('OMG another one') +
                    CHANGELOG_BAD_EPILOGUE +
                    CHANGELOG_EPILOGUE)

        with app.app_context():
            process_changelog_consistency('repo', '1234', 'installation')

        assert self.issues.call_count == 1
        self.submit_comment.assert_called_with(
            expected, comment_id=None, return_url=True)
        self.set_status.assert_called_with(
            'failure', 'There were failures in checks - see '
            'comments by @astropy-bot above', 'astropy-bot', target_url='url')

    def test_experimental(self):

        # Pull request is experimental. Don't check change log yet but
        # leave a comment.

        self.changelog_cfg.return_value = True
        self.labels.return_value = ['Experimental']
        expected = (CHANGELOG_PROLOGUE.format(user='user') +
                    CHANGELOG_NOT_DONE.format(
                        status='an experimental',
                        is_done='discussion in settled') +
                    CHANGELOG_EPILOGUE)

        with app.app_context():
            process_changelog_consistency('repo', '1234', 'installation')

        assert self.issues.call_count == 0
        self.submit_comment.assert_called_with(
            expected, comment_id=None, return_url=True)
        self.set_status.assert_called_with(
            'failure', 'There were failures in checks - see '
            'comments by @astropy-bot above', 'astropy-bot', target_url='url')

    def test_work_in_progress(self):

        # Pull request is work in progress. Don't check change log yet but
        # leave a comment.

        self.changelog_cfg.return_value = True
        self.labels.return_value = ['Work in progress']
        expected = (CHANGELOG_PROLOGUE.format(user='user') +
                    CHANGELOG_NOT_DONE.format(
                        status='a work in progress',
                        is_done='is ready for review') +
                    CHANGELOG_EPILOGUE)

        with app.app_context():
            process_changelog_consistency('repo', '1234', 'installation')

        assert self.issues.call_count == 0
        self.submit_comment.assert_called_with(
            expected, comment_id=None, return_url=True)
        self.set_status.assert_called_with(
            'failure', 'There were failures in checks - see '
            'comments by @astropy-bot above', 'astropy-bot', target_url='url')
