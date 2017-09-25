import time
from mock import MagicMock

from ..github_api import RepoHandler, IssueHandler
from ..issues import process_issues, ISSUE_CLOSE_EPILOGUE, ISSUE_CLOSE_WARNING


def test_process_issues():

    now = time.time()

    RepoHandler.get_issues = MagicMock(return_value=['123'])
    IssueHandler.get_label_added_date = MagicMock(return_value=now - 180)
    IssueHandler.find_comments = MagicMock(side_effect=[['1']])
    IssueHandler.submit_comment = MagicMock()
    IssueHandler.close = MagicMock()

    process_issues('repo', 'installation')

    RepoHandler.get_issues.assert_called_with('open', 'Close?')
    IssueHandler.get_label_added_date.assert_called_with('Close?')

    IssueHandler.submit_comment.call_count == 0
    IssueHandler.close.call_count == 0

    IssueHandler.submit_comment.reset()
    IssueHandler.close.reset()

    IssueHandler.find_comments = MagicMock(side_effect=[[]])

    process_issues('repo', 'installation')

    IssueHandler.submit_comment.call_count == 1
    expected = ISSUE_CLOSE_EPILOGUE
    IssueHandler.submit_comment.assert_called_with(expected)
    IssueHandler.close.call_count == 1

    IssueHandler.submit_comment.reset()
    IssueHandler.close.reset()

    IssueHandler.get_label_added_date = MagicMock(return_value=now - 90)
    IssueHandler.find_comments = MagicMock(side_effect=[['1']])

    process_issues('repo', 'installation')

    IssueHandler.submit_comment.call_count == 0
    IssueHandler.close.call_count == 0

    IssueHandler.submit_comment.reset()
    IssueHandler.close.reset()

    IssueHandler.find_comments = MagicMock(side_effect=[[]])

    process_issues('repo', 'installation')

    IssueHandler.submit_comment.call_count == 1
    expected = ISSUE_CLOSE_WARNING.format(pasttime='a minute ago', futuretime='a minute')
    IssueHandler.submit_comment.assert_called_with(expected)
    IssueHandler.close.call_count == 1

    IssueHandler.submit_comment.reset()
    IssueHandler.close.reset()

    IssueHandler.get_label_added_date = MagicMock(return_value=now - 30)
    IssueHandler.find_comments = MagicMock()

    process_issues('repo', 'installation')

    IssueHandler.find_comments.call_count == 0
    IssueHandler.submit_comment.call_count == 0
    IssueHandler.close.call_count == 0
