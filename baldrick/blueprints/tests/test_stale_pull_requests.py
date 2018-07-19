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
            response = self.client.post('/close_stale_pull_requests', data=json.dumps(data),
                                        content_type='application/json')
            assert response.data == b''
            assert p.call_count == 1

    @patch.object(app, 'cron_token', '12345')
    def test_invalid_cron(self):
        data = {'repository': 'test-repo', 'cron_token': '12344', 'installation': '123'}
        with patch('changebot.blueprints.stale_pull_requests.process_pull_requests') as p:
            response = self.client.post('/close_stale_pull_requests', data=json.dumps(data),
                                        content_type='application/json')
            assert response.data == b'Incorrect cron_token'
            assert p.call_count == 0

    @patch.object(app, 'cron_token', '12345')
    def test_missing_keyword(self):
        data = {'cron_token': '12344', 'installation': '123'}
        with patch('changebot.blueprints.stale_pull_requests.process_pull_requests') as p:
            response = self.client.post('/close_stale_pull_requests', data=json.dumps(data),
                                        content_type='application/json')
            assert response.data == b'Payload mising repository'
            assert p.call_count == 0


@patch.object(app, 'stale_pull_requests_close', True)
@patch.object(app, 'stale_pull_requests_close_seconds', 20)
@patch.object(app, 'stale_pull_requests_warn_seconds', 220)
class TestProcessIssues:

    def setup_method(self, method):

        self.patch_repo_config = patch.object(RepoHandler, 'get_config_value')
        self.patch_open_pull_requests = patch.object(RepoHandler, 'open_pull_requests')
        self.patch_labels = patch.object(PullRequestHandler, 'labels', new_callable=PropertyMock)
        self.patch_last_commit_date = patch.object(PullRequestHandler, 'last_commit_date', new_callable=PropertyMock)
        self.patch_last_comment_date = patch.object(PullRequestHandler, 'last_comment_date')
        self.patch_find_comments = patch.object(PullRequestHandler, 'find_comments')
        self.patch_submit_comment = patch.object(PullRequestHandler, 'submit_comment')
        self.patch_close = patch.object(PullRequestHandler, 'close')
        self.patch_set_labels = patch.object(PullRequestHandler, 'set_labels')

        self.autoclose_stale = self.patch_repo_config.start()
        self.open_pull_requests = self.patch_open_pull_requests.start()
        self.labels = self.patch_labels.start()
        self.last_commit_date = self.patch_last_commit_date.start()
        self.last_comment_date = self.patch_last_comment_date.start()
        self.find_comments = self.patch_find_comments.start()
        self.submit_comment = self.patch_submit_comment.start()
        self.close = self.patch_close.start()
        self.set_labels = self.patch_set_labels.start()

    def teardown_method(self, method):

        self.patch_repo_config.stop()
        self.patch_open_pull_requests.stop()
        self.patch_labels.stop()
        self.patch_last_commit_date.stop()
        self.patch_last_comment_date.stop()
        self.patch_find_comments.stop()
        self.patch_submit_comment.stop()
        self.patch_close.stop()
        self.patch_set_labels.stop()

    def test_close_comment_exists(self):

        # Time is beyond close deadline, and there is already a comment. In this
        # case no new comment should be posted and the issue should be kept open
        # since this likely indicates the issue was open again manually.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 241
        self.last_comment_date.return_value = now() - 241
        self.find_comments.return_value = ['1']
        self.labels.return_value = ['io.fits', 'Bug']

        with app.app_context():
            # The list() call is to forge the generator to run fully
            list(process_pull_requests('repo', 'installation'))

        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0
        assert self.set_labels.call_count == 0

    def test_close(self):

        # Time is beyond close deadline, and there is no closing comment yet so
        # the closing comment can be posted and the issue closed. In this case
        # there is already also a warning comment posted already.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 241
        self.last_comment_date.return_value = now() - 21
        self.find_comments.return_value = []

        with app.app_context():
            # The list() call is to forge the generator to run fully
            list(process_pull_requests('repo', 'installation'))

        assert self.submit_comment.call_count == 1
        expected = PULL_REQUESTS_CLOSE_EPILOGUE
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 1
        assert self.set_labels.call_count == 1

    def test_close_noclose(self):

        # Time is beyond close deadline, and there is no comment yet but the
        # YAML says don't autoclose.

        self.autoclose_stale.return_value = False
        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 241
        self.last_comment_date.return_value = now() - 21
        self.find_comments.return_value = []

        with app.app_context():
            # The list() call is to forge the generator to run fully
            list(process_pull_requests('repo', 'installation'))

        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0
        assert self.set_labels.call_count == 0

    def test_close_disabled(self):

        # Time is beyond close deadline, and there is no comment yet but the
        # global option to allow closing has not been enabled. Since there is no
        # comment, the warning gets posted (rather than the 'epilogue')

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 241
        self.last_comment_date.return_value = None
        self.find_comments.return_value = []

        with app.app_context():
            with patch.object(app, 'stale_pull_requests_close', False):
                # The list() call is to forge the generator to run fully
                list(process_pull_requests('repo', 'installation'))

        assert self.submit_comment.call_count == 1
        expected = PULL_REQUESTS_CLOSE_WARNING.format(pasttime='4 minutes', futuretime='20 seconds')
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 0
        assert self.set_labels.call_count == 0

    def test_close_keep_open_label(self):

        # Time is beyond close deadline, and there is no comment yet but there
        # is a keep-open label so don't do anything.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 241
        self.last_comment_date.return_value = None
        self.find_comments.return_value = []
        self.labels.return_value = ['keep-open']

        with app.app_context():
            with patch.object(app, 'stale_pull_requests_close', False):
                # The list() call is to forge the generator to run fully
                list(process_pull_requests('repo', 'installation'))

        assert self.submit_comment.call_count == 0

    def test_warn_comment_exists(self):

        # Time is beyond warn deadline but within close deadline. There is
        # already a warning, so don't do anything.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 241
        self.last_comment_date.return_value = now() - 18
        self.find_comments.return_value = ['1']

        with app.app_context():
            # The list() call is to forge the generator to run fully
            list(process_pull_requests('repo', 'installation'))

        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0
        assert self.set_labels.call_count == 0

    def test_warn(self):

        # Time is beyond warn deadline but within close deadline. There isn't a
        # comment yet, so a comment should be posted.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 221
        self.last_comment_date.return_value = None
        self.find_comments.return_value = []

        with app.app_context():
            # The list() call is to forge the generator to run fully
            list(process_pull_requests('repo', 'installation'))

        assert self.submit_comment.call_count == 1
        expected = PULL_REQUESTS_CLOSE_WARNING.format(pasttime='3 minutes', futuretime='20 seconds')
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 0
        assert self.set_labels.call_count == 0

    def test_warn_even_if_long_time(self):

        # Time is way beyond warn deadline. There isn't a comment yet, so a
        # warning comment should be posted.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 2000
        self.last_comment_date.return_value = None
        self.find_comments.return_value = []

        with app.app_context():
            # The list() call is to forge the generator to run fully
            list(process_pull_requests('repo', 'installation'))

        assert self.submit_comment.call_count == 1
        expected = PULL_REQUESTS_CLOSE_WARNING.format(pasttime='33 minutes', futuretime='20 seconds')
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 0
        assert self.set_labels.call_count == 0

    def test_keep_open(self):

        # Time is before warn deadline so don't do anything.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 210
        self.last_comment_date.return_value = None
        self.find_comments.return_value = []

        with app.app_context():
            # The list() call is to forge the generator to run fully
            list(process_pull_requests('repo', 'installation'))

        assert self.find_comments.call_count == 0
        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0
        assert self.set_labels.call_count == 0

    def test_warn_before_commit(self):

        # If a commit is more recent than the latest warning, ignore the latest
        # warning and warn again.

        self.open_pull_requests.return_value = ['123']
        self.last_commit_date.return_value = now() - 221
        self.last_comment_date.return_value = now() - 300
        self.find_comments.return_value = []

        with app.app_context():
            # The list() call is to forge the generator to run fully
            list(process_pull_requests('repo', 'installation'))

        assert self.submit_comment.call_count == 1
        expected = PULL_REQUESTS_CLOSE_WARNING.format(pasttime='3 minutes', futuretime='20 seconds')
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 0
        assert self.set_labels.call_count == 0
