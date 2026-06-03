"""
A simple plugin which responds to new PRs and sends a configured welcome message.
"""
from loguru import logger

from baldrick.plugins.github_pull_requests import pull_request_handler


@pull_request_handler
def send_welcome_message(pr_handler, repo_handler, payload):
    # Only react on a new PR
    if payload['action'] != 'opened':
        return

    cl_config = pr_handler.get_config_value('welcome_message', {})
    message = cl_config.get('message', False)
    if not message:
        logger.debug("Skipping welcome message, as no message set in config.")
        return None

    pr_handler.submit_comment(message)
