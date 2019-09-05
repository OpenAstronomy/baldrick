from loguru import logger

from baldrick.plugins.github_pull_requests import pull_request_handler

MISSING_MESSAGE = 'This pull request has no milestone set.'
PRESENT_MESSAGE = 'This pull request has a milestone set.'


@pull_request_handler
def process_milestone(pr_handler, repo_handler):
    """
    A very simple set a failing status if the milestone is not set.
    """
    mc_config = pr_handler.get_config_value("milestones", {})
    if not mc_config.get('enabled', False):
        logger.debug("Skipping milestone plugin as disabled in config")
        return

    logger.debug(f"Checking milestones on {pr_handler.repo}#{pr_handler.number}")

    fail_message = mc_config.get("missing_message", MISSING_MESSAGE)
    pass_message = mc_config.get("present_message", PRESENT_MESSAGE)

    if pr_handler.milestone:
        return {'milestone': {'description': pass_message, 'state': 'success'}}
    else:
        return {'milestone': {'description': fail_message, 'state': 'failure'}}
