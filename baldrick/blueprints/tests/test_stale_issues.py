import json
import time
from mock import patch

from changebot.webapp import app
from changebot.github.github_api import RepoHandler, IssueHandler
from changebot.blueprints.stale_issues import (process_issues,
                                               ISSUE_CLOSE_EPILOGUE,
                                               ISSUE_CLOSE_WARNING)


def now():
    return time.time()


class TestHook:

    def setup_method(self, method):
        self.client = app.test_client()

    @patch.object(app, 'cron_token', '12345')
    def test_valid(self):
        data = {'repository': 'test-repo', 'cron_token': '12345', 'installation': '123'}
        with patch('changebot.blueprints.stale_issues.process_issues') as p:
            self.client.post('/close_stale_issues', data=json.dumps(data),
                             content_type='application/json')
            assert p.call_count == 1

    @patch.object(app, 'cron_token', '12345')
    def test_invalid_cron(self):
        data = {'repository': 'test-repo', 'cron_token': '12344', 'installation': '123'}
        with patch('changebot.blueprints.stale_issues.process_issues') as p:
            self.client.post('/close_stale_issues', data=json.dumps(data),
                             content_type='application/json')
            assert p.call_count == 0

    @patch.object(app, 'cron_token', '12345')
    def test_missing_keyword(self):
        data = {'cron_token': '12344', 'installation': '123'}
        with patch('changebot.blueprints.stale_issues.process_issues') as p:
            self.client.post('/close_stale_issues', data=json.dumps(data),
                             content_type='application/json')
            assert p.call_count == 0


@patch.object(app, 'stale_issue_close', True)
@patch.object(app, 'stale_issue_close_seconds', 34442)
@patch.object(app, 'stale_issue_warn_seconds', 14122)
class TestProcessIssues:

    def setup_method(self, method):

        self.patch_get_issues = patch.object(RepoHandler, 'get_issues')
        self.patch_submit_comment = patch.object(IssueHandler, 'submit_comment')
        self.patch_close = patch.object(IssueHandler, 'close')
        self.patch_get_label_added_date = patch.object(IssueHandler, 'get_label_added_date')
        self.patch_find_comments = patch.object(IssueHandler, 'find_comments')

        self.get_issues = self.patch_get_issues.start()
        self.submit_comment = self.patch_submit_comment.start()
        self.close = self.patch_close.start()
        self.get_label_added_date = self.patch_get_label_added_date.start()
        self.find_comments = self.patch_find_comments.start()

    def teardown_method(self, method):

        self.patch_get_issues.stop()
        self.patch_submit_comment.stop()
        self.patch_close.stop()
        self.patch_get_label_added_date.stop()
        self.patch_find_comments.stop()

    def test_close_comment_exists(self):

        # Time is beyond close deadline, and there is already a comment. In this
        # case no new comment should be posted and the issue should be kept open
        # since this likely indicates the issue was open again manually.

        self.get_issues.return_value = ['123']
        self.get_label_added_date.return_value = now() - 34443
        self.find_comments.return_value = ['1']

        with app.app_context():
            process_issues('repo', 'installation')

        self.get_issues.assert_called_with('open', 'Close?')
        self.get_label_added_date.assert_called_with('Close?')

        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0

    def test_close(self):

        # Time is beyond close deadline, and there is no comment yet so the
        # closing comment can be posted and the issue closed.

        self.get_issues.return_value = ['123']
        self.get_label_added_date.return_value = now() - 34443
        self.find_comments.return_value = []

        with app.app_context():
            process_issues('repo', 'installation')

        assert self.submit_comment.call_count == 1
        expected = ISSUE_CLOSE_EPILOGUE
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 1

    def test_close_disabled(self):

        # Second case: time is beyond close deadline, and there is no comment yet
        # but the global option to allow closing has not been enabled. Since there
        # is no comment, the warning gets posted (rather than the 'epilogue')

        self.get_issues.return_value = ['123']
        self.get_label_added_date.return_value = now() - 34443
        self.find_comments.return_value = []

        with app.app_context():
            with patch.object(app, 'stale_issue_close', False):
                process_issues('repo', 'installation')

        assert self.submit_comment.call_count == 1
        expected = ISSUE_CLOSE_WARNING.format(pasttime='3 hours ago', futuretime='5 hours')
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 0

    def test_warn_comment_exists(self):

        # Time is beyond warn deadline but within close deadline. There is
        # already a warning, so don't do anything.

        self.get_issues.return_value = ['123']
        self.get_label_added_date.return_value = now() - 34400
        self.find_comments.return_value = ['1']

        with app.app_context():
            process_issues('repo', 'installation')

        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0

    def test_warn(self):

        # Time is beyond warn deadline but within close deadline. There isn't a
        # comment yet, so a comment should be posted.

        self.get_issues.return_value = ['123']
        self.get_label_added_date.return_value = now() - 34400
        self.find_comments.return_value = []

        with app.app_context():
            process_issues('repo', 'installation')

        assert self.submit_comment.call_count == 1
        expected = ISSUE_CLOSE_WARNING.format(pasttime='3 hours ago', futuretime='5 hours')
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 0

    def test_keep_open(self):

        # Time is before warn deadline so don't do anything.

        self.get_issues.return_value = ['123']
        self.get_label_added_date.return_value = now() - 14000
        self.find_comments.return_value = []

        with app.app_context():
            process_issues('repo', 'installation')

        assert self.find_comments.call_count == 0
        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0
