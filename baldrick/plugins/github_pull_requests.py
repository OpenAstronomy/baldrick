import copy

from flask import current_app
from loguru import logger

from baldrick.github.github_api import RepoHandler, PullRequestHandler
from baldrick.blueprints.github import github_webhook_handler
from baldrick.utils import insert_special_message

__all__ = ['pull_request_handler']

PULL_REQUEST_CHECKS = dict()


def pull_request_handler(actions=None):
    """
    A decorator to add functions to the pull request checker.

    By default, functions decorated with this decorator will be passed events
    which match the following actions:

    * unlabeled
    * labeled
    * synchronize
    * opened
    * milestoned
    * demilestoned

    However, you may pass in a list of strings with subsets of these actions to
    control when the checks are run.

    They will be passed ``(pr_handler, repo_handler)`` and are expected to
    return a dictionary where the key is a unique string that refers to the
    specific check that has been made, and the values are dictionaries with any
    arguments to the `~baldrick.github.github_api.PullRequestHandler.set_check`
    method. Required ones are:

    * ``conclusion`` is a string giving the state for the latest commit (one of
      ``success``, ``failure``, ``neutral``, ``cancelled``, ``timed_out``, or
      ``action_required``).
    * ``title`` is the message to be shown in the status line of the PR

    Common optional ones are:

    * ``name``:: The name of the check in the status line of the PR.
    * ``summary``:: A summary of the check to be put on the check page.
    * ``target_url``: A URL to link to in the status.
    """

    if callable(actions):

        # Decorator is being used without brackets and the actions argument
        # is just the function itself.
        PULL_REQUEST_CHECKS[actions] = None

        return actions

    else:

        def wrapper(func):
            PULL_REQUEST_CHECKS[func] = actions
            return func

        return wrapper


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

    is_new = (event == 'pull_request') & (payload['action'] == 'opened')

    logger.debug(f"Processing event {event} #{number} on {repo_handler.repo}")

    return process_pull_request(
        repo_handler.repo, number, repo_handler.installation,
        action=payload['action'], is_new=is_new)


def process_pull_request(repository, number, installation, action,
                         is_new=False):

    # TODO: cache handlers and invalidate the internal cache of the handlers on
    # certain events.
    pr_handler = PullRequestHandler(repository, number, installation)

    pr_config = pr_handler.get_config_value("pull_requests", {})
    if not pr_config.get("enabled", False):
        msg = "Skipping PR checks, disabled in config."
        logger.debug(msg)
        return msg

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
                pr_handler.set_check(
                    current_app.bot_username,
                    title="Skipping checks due to {0} label".format(label),
                    name=current_app.bot_username,
                    status='completed', conclusion='failure')
            return

    results = {}
    for function, actions in PULL_REQUEST_CHECKS.items():
        if actions is None or action in actions:
            result = function(pr_handler, repo_handler)
            # Ignore skipped checks
            if result is not None:
                # Map old plugin keys to new checks names.
                # It's possible that the hook returns {}
                for context, check in result.items():
                    if check is not None:
                        title = check.pop('description', None)
                        if title:
                            logger.warning(
                                f"'description' is deprecated as a key in the return value from {function},"
                                " it will be interpreted as 'title'")
                            check['title'] = title
                        conclusion = check.pop('state', None)
                        if conclusion:
                            logger.warning(
                                f"'state' is deprecated as a key in the return value from {function},"
                                "it will be interpreted as 'conclusion'.")
                            check['conclusion'] = conclusion
                    result[context] = check
                results.update(result)

    # Get existing checks from our app, for the 'head' commit
    existing_checks = pr_handler.list_checks(only_ours=True)
    # For each existing check, see if it needs updating or skipping
    new_results = copy.copy(results)
    for external_id, check in existing_checks.items():
        if external_id in results.keys():
            details = new_results.pop(external_id)
            # Update the previous check with the new check (this includes the check_id to update)
            check.update(details)
            # Send the check to be updated
            pr_handler.set_check(**check)
        else:
            # If check is in existing_checks but not results mark it as skipped.
            check.update({
                'title': 'This check has been skipped.',
                'status': 'completed',
                'conclusion': 'neutral'})
            pr_handler.set_check(**check)

    # Any keys left in results are new checks we haven't sent on this commit yet.
    for external_id, details in sorted(new_results.items()):
        pr_handler.set_check(external_id, status="completed", **details)

    # Also set the general 'single' status check as a skipped check if it
    # is present
    if current_app.bot_username in new_results.keys():
        check.update({
            'title': 'This check has been skipped.',
            'commit_hash': 'head',
            'status': 'completed',
            'conclusion': 'neutral'})
        pr_handler.set_check(**check)

    # Special message for a special day
    not_boring = pr_handler.get_config_value('not_boring', cfg_default=True)
    if not_boring:  # pragma: no cover
        special_msg = ''
        if is_new:  # Always be snarky for new PR
            special_msg = insert_special_message('')
        else:
            import random
            tensided_dice_roll = random.randrange(10)
            if tensided_dice_roll == 9:  # 1 out of 10 for subsequent remarks
                special_msg = insert_special_message('')
        if special_msg:
            pr_handler.submit_comment(special_msg)

    return 'Finished pull requests checks'
