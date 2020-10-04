"""
A plugin which reacts to comments on PRs and can add a changelog.
"""
import re
from loguru import logger

from baldrick.github.github_api import PullRequestHandler, IssueHandler
from baldrick.blueprints.github import github_webhook_handler

ISSUE_COMMENT_MATCHERS = {}
PR_COMMENT_MATCHERS = {}


@github_webhook_handler
def handle_issue_comments(repo_handler, payload, headers):

    event = headers['X-GitHub-Event']
    if event != 'issue_comment':
        return "Not a pull_request or issues event"

    number = payload['issue']['number']

    issue_handler = IssueHandler(repo_handler.repo, number, repo_handler.installation)
    if 'pull_request' in payload['issue']:
        issue_handler = PullRequestHandler(repo_handler.repo, number, repo_handler.installation)

    process_issue_comment(issue_handler, repo_handler, payload['comment']['body'], payload)


def match_issue_comment(regex, issue_type="both"):
    """
    A decorator used to call a plugin on a issue comment.

    Parameters
    ----------
    regex : `str`
        The regex to apply to the comment.

    issue_type : `str` {'issue', 'pull', 'both'}
        The type of issue to match on. Defaults to 'both' to match comments on issues and PRs.
    """
    def wrapper(func):
        if issue_type in ('issue', 'both'):
            ISSUE_COMMENT_MATCHERS[regex] = func
            return func
        if issue_type in ('pull', 'both'):
            PR_COMMENT_MATCHERS[regex] = func
            return func

        raise ValueError("issue_type must be one one 'issue', 'pull' or 'both'")

    return wrapper


def process_issue_comment(issue_handler, repo_handler, comment, payload):
    logger.trace(f"Processing comment {comment} on {issue_handler.repo}#{issue_handler.number}.")

    if 'pull_request' in payload['issue']:
        for expression, func in PR_COMMENT_MATCHERS.items():
            logger.trace(f"Testing {expression} for pull_request.")
            match = re.search(expression, comment, False)
            if match:
                logger.trace(f"{expression} matched calling {func}")
                func(issue_handler, repo_handler, comment, payload)
    else:
        for expression, func in ISSUE_COMMENT_MATCHERS.items():
            logger.trace(f"Testing {expression} for issue.")
            match = re.search(expression, comment, False)
            if match:
                logger.trace(f"{expression} matched calling {func}")
                func(issue_handler, repo_handler, comment, payload)
