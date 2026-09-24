from loguru import logger

from baldrick.plugins.github_pull_requests import pull_request_handler

BLOCKED_MESSAGE = 'This pull request is blocked from being merged by labels.'
MERGEABLE_MESSAGE = 'This pull request is not blocked from being merged by labels.'

@pull_request_handler
def fail_check_labels(pr_handler, repo_handler):
    """
    Set a failing status if any labels in the config are set
    """
    bl_config = pr_handler.get_config_value("fail_check_labels", {})
    if not bl_config.get('enabled', False):
        logger.debug("Skipping fail label check plugin as disabled in config")
        return

    logger.debug(f"Checking for blocking labels on {pr_handler.repo}#{pr_handler.number}")

    fail_message = bl_config.get("label_present_message", BLOCKED_MESSAGE)
    pass_message = bl_config.get("label_absent_message", MERGEABLE_MESSAGE)

    pr_labels = set(pr_handler.labels)
    blocking_labels = set(cl_config.get('labels', [])

    if pr_labels.intersection(blocking_labels):
        return {'blocking_labels': {
            'title': fail_message,
            'conclusion': 'failure',
            'summary': mc_config.get("label_present_message_long", '')
        }}
    else:
        return {'blocking_labels': {
            'title': pass_message,
            'conclusion': 'success',
            'summary': mc_config.get("label_absent_message_long", '')
        }}
