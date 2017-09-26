import time
from mock import MagicMock

from ..github_api import RepoHandler, IssueHandler
from ..issues import process_issues, ISSUE_CLOSE_EPILOGUE, ISSUE_CLOSE_WARNING


def test_process_issues():

    now = time.time()

    RepoHandler.get_issues = MagicMock(return_value=['123'])
    IssueHandler.submit_comment = MagicMock()
    IssueHandler.close = MagicMock()

    # First case: time is beyond close deadline, and there is already a
    # comment. In this case no new comment should be posted and the issue should
    # be kept open since this likely indicates the issue was open again
    # manually.

    IssueHandler.get_label_added_date = MagicMock(return_value=now - 180)
    IssueHandler.find_comments = MagicMock(side_effect=[['1']])

    process_issues('repo', 'installation')

    RepoHandler.get_issues.assert_called_with('open', 'Close?')
    IssueHandler.get_label_added_date.assert_called_with('Close?')

    assert IssueHandler.submit_comment.call_count == 0
    assert IssueHandler.close.call_count == 0

    IssueHandler.submit_comment.reset_mock()
    IssueHandler.close.reset_mock()

    # Second case: time is beyond close deadline, and there is no comment yet
    # so the closing comment can be posted and the issue closed.

    IssueHandler.find_comments = MagicMock(side_effect=[[]])

    process_issues('repo', 'installation')

    assert IssueHandler.submit_comment.call_count == 1
    expected = ISSUE_CLOSE_EPILOGUE
    IssueHandler.submit_comment.assert_called_with(expected)
    assert IssueHandler.close.call_count == 1

    IssueHandler.submit_comment.reset_mock()
    IssueHandler.close.reset_mock()

    # Third case: time is beyond warn deadline but within close deadline. There
    # is already a warning, so don't do anything.

    IssueHandler.get_label_added_date = MagicMock(return_value=now - 90)
    IssueHandler.find_comments = MagicMock(side_effect=[['1']])

    process_issues('repo', 'installation')

    assert IssueHandler.submit_comment.call_count == 0
    assert IssueHandler.close.call_count == 0

    IssueHandler.submit_comment.reset_mock()
    IssueHandler.close.reset_mock()

    # Fourth case: time is beyond warn deadline but within close deadline. There
    # isn't a comment yet, so a comment should be posted.

    IssueHandler.find_comments = MagicMock(side_effect=[[]])

    process_issues('repo', 'installation')

    assert IssueHandler.submit_comment.call_count == 1
    expected = ISSUE_CLOSE_WARNING.format(pasttime='a minute ago', futuretime='a minute')
    IssueHandler.submit_comment.assert_called_with(expected)
    assert IssueHandler.close.call_count == 0

    IssueHandler.submit_comment.reset_mock()
    IssueHandler.close.reset_mock()

    # Fifth case: time is before warn deadline so don't do anything.

    IssueHandler.get_label_added_date = MagicMock(return_value=now - 30)
    IssueHandler.find_comments = MagicMock()

    process_issues('repo', 'installation')

    assert IssueHandler.find_comments.call_count == 0
    assert IssueHandler.submit_comment.call_count == 0
    assert IssueHandler.close.call_count == 0
