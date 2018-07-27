from .github_pull_requests import pull_request_handler


MISSING_MESSAGE = 'This pull request has no milestone set.'
PRESENT_MESSAGE = 'This pull request has a milestone set.'


@pull_request_handler
def process_milestone(pr_handler, repo_handler):
    """
    A very simple set a failing status if the milestone is not set.
    """

    mc_config = repo_handler.get_config_value("milestones", None)

    if mc_config is None:
        return {}

    fail_message = mc_config.get("missing_message", MISSING_MESSAGE)
    pass_message = mc_config.get("present_message", PRESENT_MESSAGE)

    if pr_handler.milestone:
        return {'milestone': {'message': pass_message, 'status': 'success'}}
    else:
        return {'milestone': {'message': fail_message, 'status': 'failure'}}
