from flask import current_app

from baldrick.github.github_api import RepoHandler, PullRequestHandler
from baldrick.blueprints.github import github_webhook_handler
from baldrick.plugins.utils import get_config_with_app_defaults

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
    return a dictionary where the key is a unique string that refers to the
    specific check that has been made, and the values are a tuple of
    ``(message, status``), where ``message`` is the message to be shown in the
    status or in the comment and ``status`` is a boolean that indicates whether
    the build has succeeded (``True``) or failed (``False``).
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
    post_comment = pr_config.get("post_pr_comment", False)

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

    results = {}
    for function in PULL_REQUEST_CHECKS:
        result = function(pr_handler, repo_handler)
        results.update(result)

    failures = [message for message, status in results.values() if not status]

    if post_comment:

        # Post all failures in a comment, and have a single status check

        if failures:

            pull_request_prologue = get_config_with_app_defaults(pr_handler, 'pull_request_prologue', default='')
            pull_request_epilogue = get_config_with_app_defaults(pr_handler, 'pull_request_epilogue', default='')

            message = pull_request_prologue.format(pr_handler=pr_handler, repo_handler=repo_handler)
            message += ''.join(failures) + pull_request_epilogue
            comment_url = pr_handler.submit_comment(message, comment_id=comment_id,
                                                    return_url=True)

            pr_handler.set_status('failure',
                                  pr_config.get("pr_failed_status", "Failed some checks"),
                                  current_app.bot_username, target_url=comment_url)

        else:

            all_passed_message = pr_config.get("all_passed_message", '')
            all_passed_message = all_passed_message.format(pr_handler=pr_handler, repo_handler=repo_handler)
            if all_passed_message:
                pr_handler.submit_comment(all_passed_message, comment_id=comment_id)

            pr_handler.set_status('success',
                                  pr_config.get("pr_passed_status", "Passed all checks"),
                                  current_app.bot_username)

    else:

        # Post each failure as a status

        for context, (message, status) in sorted(results.items()):

            pr_handler.set_status('success' if status else 'failure', message,
                                  current_app.bot_username + ':' + context)

    return 'Finished pull requests checks'
