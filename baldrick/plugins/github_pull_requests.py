from flask import current_app

from baldrick.github.github_api import RepoHandler, PullRequestHandler
from baldrick.blueprints.github import github_webhook_handler
from baldrick.utils import insert_special_message

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
    specific check that has been made, and the values are dictionaries with
    the following keys:

    * ``status`` is a string giving the state for the latest commit (one of
      ``success``, ``failure``, ``error``, or ``pending``).
    * ``message``: the message to be shown in the status
    * ``target_url`` (optional): a URL to link to in the status
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

    pr_config = pr_handler.get_config_value("pull_requests", {})
    if not pr_config.get("enabled", False):
        return "Skipping PR checks, disabled in config."

    # Disable if the config is not present
    if pr_config is None:
        return

    # Don't comment on closed PR
    if pr_handler.is_closed:
        return "Pull request already closed, no need to check"

    repo_handler = RepoHandler(pr_handler.head_repo_name,
                               pr_handler.head_branch, installation)

    # First check whether there are labels that indicate the checks should be
    # skipped

    skip_labels = pr_config.get("skip_labels", [])
    skip_fails = pr_config.get("skip_fails", True)

    for label in pr_handler.labels:
        if label in skip_labels:
            if skip_fails:
                pr_handler.set_status('failure', "Skipping checks due to {0} label".format(label), current_app.bot_username)
            return

    results = {}
    for function in PULL_REQUEST_CHECKS:
        result = function(pr_handler, repo_handler)
        # Ignore skipped checks
        if result is not None:
            results.update(result)

    # Special message for a special day
    not_boring = pr_handler.get_config_value('not_boring', cfg_default=True)
    if not_boring:  # pragma: no cover
        import numpy as np
        tensided_dice_roll = np.random.choice(np.arange(10))
        if tensided_dice_roll == 9:  # 1 out of 10
            special_msg = insert_special_message('')
            if special_msg:
                pr_handler.submit_comment(special_msg)

    # Post each failure as a status

    existing_statuses = pr_handler.list_statuses()

    for context, details in sorted(results.items()):

        full_context = current_app.bot_username + ':' + context

        # NOTE: we could in principle check if the status has been posted
        # before, and if so not post it again, but we had this in the past
        # and there were some strange caching issues where GitHub would
        # return old status messages, so we avoid doing that.

        pr_handler.set_status(details['state'], details['description'],
                              full_context,
                              target_url=details.get('target_url'))

    # For statuses that have been skipped this time but existed before, set
    # status to pass and set message to say skipped

    for full_context in existing_statuses:

        if full_context.startswith(current_app.bot_username + ':'):
            context = full_context[len(current_app.bot_username) + 1:]
            if context not in results:
                pr_handler.set_status('success', 'This check has been skipped',
                                      current_app.bot_username + ':' + context)

        # Also set the general 'single' status check as a skipped check if it
        # is present
        if full_context == current_app.bot_username:
            pr_handler.set_status('success', 'This check has been skipped',
                                  current_app.bot_username)

    return 'Finished pull requests checks'
