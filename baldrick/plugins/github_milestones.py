from flask import current_app

from .pull_request_checker import pull_request_check


MISSING_MESSAGE = 'This pull request has no milestone set.'
PRESENT_MESSAGE = 'This pull request has a milestone set.'


@pull_request_check
def process_milestone(pr_handler, repo_handler):
    """
    A very simple set a failing status if the milestone is not set.
    """
    mc_config = repo_handler.get_config_value("milestones", None)

    if mc_config is None:
        return [], None

    fail_message = mc_config.get("missing_message", MISSING_MESSAGE)
    pass_message = mc_config.get("present_message", PRESENT_MESSAGE)

    if not repo_handler.get_config_value('pull_requests', {}).get("post_pr_comment", False):
        if not pr_handler.milestone:
            pr_handler.set_status(pr_handler.head_sha, 'failure', fail_message, current_app.bot_username + ": milestone")
        else:
            pr_handler.set_status(pr_handler.head_sha, 'success', pass_message, current_app.bot_username + ": milestone")

        return [], None

    else:
        if not pr_handler.milestone:
            return [fail_message], False
        else:
            return [], True
