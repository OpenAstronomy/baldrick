from flask import current_app

from baldrick.github.github_api import RepoHandler, PullRequestHandler
from baldrick.blueprints.github import github_webhook_handler

__all__ = ['pull_request_handler']

PULL_REQUEST_CHECKS = []


def pull_request_handler(func):
    """
    A decorator to add functions to the pull request checker.

    Functions decorated with this decorator will be passed events which match
    the following actions:

    * unlabeled
    * labeled
    * synchronize
    * opened
    * milestoned
    * demilestoned

    They will be passed ``(pr_handler, repo_handler)`` and are expected to
    return ``messages, status` where messages is a list of strings to be
    concatenated together with the prolog and epilogue to form a comment message
    (if this is an empty list, no comment will be posted) and status is either a
    boolean (`True` for PR passes, `False` for fail) or `None` for no status
    check.
    """
    PULL_REQUEST_CHECKS.append(func)
    return func


@github_webhook_handler
def handle_pull_requests(repo_handler, payload, headers):
    """
    Handle pull request events which match the following event types:
    """

    event = headers['X-GitHub-Event']

    if event not in ('pull_request', 'issues'):
        return "Not a pull_request or issues event"

    # We only need to listen to certain kinds of events:
    if event == 'pull_request':
        if payload['action'] not in ('unlabeled', 'labeled', 'synchronize', 'opened'):
            return "Action '" + payload['action'] + "' does not require action"
    elif event == 'issues':
        if payload['action'] not in ('milestoned', 'demilestoned'):
            return "Action '" + payload['action'] + "' does not require action"

    if event == 'pull_request':
        number = payload['pull_request']['number']
    elif event == 'issues':
        number = payload['issue']['number']
    else:
        return "Not an issue or pull request"

    return process_pull_request(repo_handler.repo, number, repo_handler.installation)


def process_pull_request(repository, number, installation):
    # TODO: cache handlers and invalidate the internal cache of the handlers on
    # certain events.
    pr_handler = PullRequestHandler(repository, number, installation)

    pr_config = pr_handler.get_config_value("pull_requests", None)

    # Disable if the config is not present
    if pr_config is None:
        return

    # Don't comment on closed PR
    if pr_handler.is_closed:
        return "Pull request already closed, no need to check"

    repo_handler = RepoHandler(pr_handler.head_repo_name,
                               pr_handler.head_branch, installation)

    def is_previous_comment(message):
        return current_app.pull_request_substring in message

    # Find previous comments by this app
    comment_ids = pr_handler.find_comments(
        f'{current_app.bot_username}[bot]', filter_keep=is_previous_comment)

    if len(comment_ids) == 0:
        comment_id = None
    else:
        comment_id = comment_ids[-1]

    comments = []
    set_status = False  # Do not send a status unless we need to.
    status = True  # True is passing
    for function in PULL_REQUEST_CHECKS:
        f_comments, f_status = function(pr_handler, repo_handler)
        if f_status is not None:
            set_status = True
            status = status and f_status
        comments += f_comments

    if comments:
        message = current_app.pull_request_prolog.format(pr_handler=pr_handler, repo_handler=repo_handler)
        message += ''.join(comments) + current_app.pull_request_epilog
        comment_url = pr_handler.submit_comment(message, comment_id=comment_id,
                                                return_url=True)
    else:
        all_passed_message = pr_config.get("all_passed_message", '')
        all_passed_message = all_passed_message.format(pr_handler=pr_handler, repo_handler=repo_handler)
        if all_passed_message:
            pr_handler.submit_comment(all_passed_message, comment_id=comment_id)

        comment_url = None
        message = ''

    if set_status:
        if status:
            pr_handler.set_status(pr_handler.head_sha, 'success',
                                  pr_config.get("pr_passed_status", "Passed all checks"),
                                  current_app.bot_username, target_url=comment_url)
        else:
            pr_handler.set_status(pr_handler.head_sha, 'failure',
                                  pr_config.get("pr_failed_status", "Failed some checks"),
                                  current_app.bot_username, target_url=comment_url)

    return message
