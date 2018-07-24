import time
from unittest.mock import patch

from baldrick.github.github_api import RepoHandler, IssueHandler
from baldrick.scripts.stale_issues import (process_issues, main,
                                           ISSUE_CLOSE_EPILOGUE,
                                           ISSUE_CLOSE_WARNING,
                                           is_close_warning,
                                           is_close_epilogue)


def test_is_close_warning():
    assert is_close_warning(ISSUE_CLOSE_WARNING)


def test_is_close_epilogue():
    assert is_close_epilogue(ISSUE_CLOSE_EPILOGUE)


def now():
    return time.time()


def test_main():

    with patch('baldrick.scripts.stale_issues.process_issues') as process:
        with patch('baldrick.scripts.stale_issues.repo_to_installation_id') as to_id:
            to_id.return_value = '12431'
            main('--repository testrepo --warn-seconds 10 --close-seconds 20'.split())
        process.assert_called_with('testrepo', '12431', warn_seconds=10, close_seconds=20)


class TestProcessIssues:

    def setup_method(self, method):

        self.patch_get_issues = patch.object(RepoHandler, 'get_issues')
        self.patch_submit_comment = patch.object(IssueHandler, 'submit_comment')
        self.patch_close = patch.object(IssueHandler, 'close')
        self.patch_get_label_added_date = patch.object(IssueHandler, 'get_label_added_date')
        self.patch_find_comments = patch.object(IssueHandler, 'find_comments')
        self.patch_set_labels = patch.object(IssueHandler, 'set_labels')

        self.get_issues = self.patch_get_issues.start()
        self.submit_comment = self.patch_submit_comment.start()
        self.close = self.patch_close.start()
        self.get_label_added_date = self.patch_get_label_added_date.start()
        self.find_comments = self.patch_find_comments.start()
        self.set_labels = self.patch_set_labels.start()

    def teardown_method(self, method):

        self.patch_get_issues.stop()
        self.patch_submit_comment.stop()
        self.patch_close.stop()
        self.patch_get_label_added_date.stop()
        self.patch_find_comments.stop()
        self.patch_set_labels.stop()

    def test_close_comment_exists(self):

        # Time is beyond close deadline, and there is already a comment. In this
        # case no new comment should be posted and the issue should be kept open
        # since this likely indicates the issue was open again manually.

        self.get_issues.return_value = ['123']
        self.get_label_added_date.return_value = now() - 34443
        self.find_comments.return_value = ['1']

        process_issues('repo', 'installation', warn_seconds=14122, close_seconds=34442)

        self.get_issues.assert_called_with('open', 'Close?')
        self.get_label_added_date.assert_called_with('Close?')

        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0
        assert self.set_labels.call_count == 0

    def test_close(self):

        # Time is beyond close deadline, and there is no comment yet so the
        # closing comment can be posted and the issue closed.

        self.get_issues.return_value = ['123']
        self.get_label_added_date.return_value = now() - 34443
        self.find_comments.return_value = []

        process_issues('repo', 'installation', warn_seconds=14122, close_seconds=34442)

        assert self.submit_comment.call_count == 1
        expected = ISSUE_CLOSE_EPILOGUE
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 1
        assert self.set_labels.call_count == 1

    def test_warn_comment_exists(self):

        # Time is beyond warn deadline but within close deadline. There is
        # already a warning, so don't do anything.

        self.get_issues.return_value = ['123']
        self.get_label_added_date.return_value = now() - 34400
        self.find_comments.return_value = ['1']

        process_issues('repo', 'installation', warn_seconds=14122, close_seconds=34442)

        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0
        assert self.set_labels.call_count == 0

    def test_warn(self):

        # Time is beyond warn deadline but within close deadline. There isn't a
        # comment yet, so a comment should be posted.

        self.get_issues.return_value = ['123']
        self.get_label_added_date.return_value = now() - 34400
        self.find_comments.return_value = []

        process_issues('repo', 'installation', warn_seconds=14122, close_seconds=34442)

        assert self.submit_comment.call_count == 1
        expected = ISSUE_CLOSE_WARNING.format(pasttime='9 hours ago', futuretime='5 hours')
        self.submit_comment.assert_called_with(expected)
        assert self.close.call_count == 0
        assert self.set_labels.call_count == 0

    def test_keep_open(self):

        # Time is before warn deadline so don't do anything.

        self.get_issues.return_value = ['123']
        self.get_label_added_date.return_value = now() - 14000
        self.find_comments.return_value = []

        process_issues('repo', 'installation', warn_seconds=14122, close_seconds=34442)

        assert self.find_comments.call_count == 0
        assert self.submit_comment.call_count == 0
        assert self.close.call_count == 0
        assert self.set_labels.call_count == 0
