from loguru import logger

from .github_pull_requests import pull_request_handler


# Only run this check once when a PR is opened.
@pull_request_handler(actions=['opened', 'synchronize'])
def check_base_branch(pr_handler, repo_handler):
    logger.trace(f'Running base branch checker for {pr_handler.repo}#{pr_handler.number}')
    cl_config = repo_handler.get_config_value("basebranch_checker", {})

    if not cl_config.get('enabled', False):
        logger.debug("Skipping base branch check plugin as disabled in config")
        return

    basebranch = cl_config.get('basebranch', 'master')
    pr_basebranch = pr_handler.base_branch

    if pr_basebranch == basebranch:
        logger.info(f'PR opened correctly against {basebranch}')
        return

    return {'basebranch': {
        'description': f'PR opened against {pr_basebranch}, not {basebranch}',
        'state': 'failure'}}
