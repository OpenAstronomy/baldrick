import json
import time
from unittest.mock import patch, PropertyMock

from changebot.webapp import app
from changebot.github.github_api import RepoHandler, PullRequestHandler
from changebot.blueprints.stale_pull_requests import (process_pull_requests,
                                                      PULL_REQUESTS_CLOSE_EPILOGUE,
                                                      PULL_REQUESTS_CLOSE_WARNING,
                                                      is_close_warning,
                                                      is_close_epilogue)


def test_is_close_warning():
    assert is_close_warning(PULL_REQUESTS_CLOSE_WARNING)


def test_is_close_epilogue():
    assert is_close_epilogue(PULL_REQUESTS_CLOSE_EPILOGUE)


def now():
    return time.time()


class TestHook:

    def setup_method(self, method):
        self.client = app.test_client()

    @patch.object(app, 'cron_token', '12345')
    def test_valid(self):
        data = {'repository': 'test-repo', 'cron_token': '12345', 'installation': '123'}
        with patch('changebot.blueprints.stale_pull_requests.process_pull_requests') as p:
            self.client.post('/close_stale_pull_requests', data=json.dumps(data),
                             content_type='application/json')
            assert p.call_count == 1

    @patch.object(app, 'cron_token', '12345')
    def test_invalid_cron(self):
        data = {'repository': 'test-repo', 'cron_token': '12344', 'installation': '123'}
        with patch('changebot.blueprints.stale_pull_requests.process_pull_requests') as p:
            self.client.post('/close_stale_pull_requests', data=json.dumps(data),
                             content_type='application/json')
            assert p.call_count == 0

    @patch.object(app, 'cron_token', '12345')
    def test_missing_keyword(self):
        data = {'cron_token': '12344', 'installation': '123'}
        with patch('changebot.blueprints.stale_pull_requests.process_pull_requests') as p:
            self.client.post('/close_stale_pull_requests', data=json.dumps(data),
                             content_type='application/json')
            assert p.call_count == 0


@patch.object(app, 'stale_pull_requests_close', True)
@patch.object(app, 'stale_pull_requests_close_seconds', 240)
@patch.object(app, 'stale_pull_requests_warn_seconds', 220)
class TestProcessIssues:

    def setup_method(self, method):

        self.patch_repo_config = patch.object(RepoHandler, 'get_config_value')
        self.patch_open_pull_requests = patch.object(RepoHandler, 'open_pull_requests')
        self.patch_labels = patch.object(PullRequestHandler, 'labels', new_callable=PropertyMock)
        self.patch_last_commit_date = patch.object(PullRequestHandler, 'last_commit_date', new_callable=PropertyMock)
        self.patch_find_comments = patch.object(PullRequestHandler, 'find_comments')
        self.patch_submit_comment = patch.object(PullRequestHandler, 'submit_comment')
        self.patch_close = patch.object(PullRequestHandler, 'close')

        self.autoclose_stale = self.patch_repo_config.start()
        self.open_pull_requests = self.patch_open_pull_requests.start()
        self.labels = self.patch_labels.start()
        self.last_commit_date = self.patch_last_commit_date.start()
        self.find_comments = self.patch_find_comments.start()
        self.submit_comment = self.patch_submit_comment.start()
        self.close = self.patch_close.start()

    def teardown_method(self, method):

        self.patch_repo_config.stop()
        self.patch_open_pull_requests.stop()
        self.patch_labels.stop()
        self.patch_last_commit_date.stop()
        self.patch_find_comments.stop()
        self.patch_submit_comment.stop()
        self.patch_close.stop()

    def test_close_comment_exists(self):

        # Time is beyond close deadline, and there is already a comment. In this
        # case no new comment should be posted and the issue should be kept open
        # since this likely indicates the issue was open again manually.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 241
        self.find_comments.return_value = ['1']
        self.labels.return_value = ['io.fits', 'Bug']

        with app.app_context():
            process_pull_requests('repo', 'installation')

        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0

    def test_close(self):

        # Time is beyond close deadline, and there is no comment yet so the
        # closing comment can be posted and the issue closed.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 241
        self.find_comments.return_value = []

        with app.app_context():
            process_pull_requests('repo', 'installation')

        assert self.submit_comment.call_count == 1
        expected = PULL_REQUESTS_CLOSE_EPILOGUE
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 1

    def test_close_noclose(self):

        # Time is beyond close deadline, and there is no comment yet but the
        # YAML says don't autoclose.

        self.autoclose_stale.return_value = False
        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 241
        self.find_comments.return_value = []

        with app.app_context():
            process_pull_requests('repo', 'installation')

        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0

    def test_close_disabled(self):

        # Time is beyond close deadline, and there is no comment yet but the
        # global option to allow closing has not been enabled. Since there is no
        # comment, the warning gets posted (rather than the 'epilogue')

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 241
        self.find_comments.return_value = []

        with app.app_context():
            with patch.object(app, 'stale_pull_requests_close', False):
                process_pull_requests('repo', 'installation')

        assert self.submit_comment.call_count == 1
        expected = PULL_REQUESTS_CLOSE_WARNING.format(pasttime='4 minutes', futuretime='20 seconds')
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 0

    def test_close_keep_open_label(self):

        # Time is beyond close deadline, and there is no comment yet but there
        # is a keep-open label

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 241
        self.find_comments.return_value = []

        with app.app_context():
            with patch.object(app, 'stale_pull_requests_close', False):
                process_pull_requests('repo', 'installation')

        assert self.submit_comment.call_count == 1
        expected = PULL_REQUESTS_CLOSE_WARNING.format(pasttime='4 minutes', futuretime='20 seconds')
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 0

    def test_warn_comment_exists(self):

        # Time is beyond warn deadline but within close deadline. There is
        # already a warning, so don't do anything.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 230
        self.find_comments.return_value = ['1']

        with app.app_context():
            process_pull_requests('repo', 'installation')

        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0

    def test_warn(self):

        # Time is beyond warn deadline but within close deadline. There isn't a
        # comment yet, so a comment should be posted.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 230
        self.find_comments.return_value = []

        with app.app_context():
            process_pull_requests('repo', 'installation')

        assert self.submit_comment.call_count == 1
        expected = PULL_REQUESTS_CLOSE_WARNING.format(pasttime='3 minutes', futuretime='20 seconds')
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 0

    def test_keep_open(self):

        # Time is before warn deadline so don't do anything.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 210
        self.find_comments.return_value = []

        with app.app_context():
            process_pull_requests('repo', 'installation')

        assert self.find_comments.call_count == 0
        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0
