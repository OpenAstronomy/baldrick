from baldrick.plugins.github_pull_requests import pull_request_handler


# Or do we want to check every push event?
@pull_request_handler(actions=['opened'])
def check_base_branch(pr_handler, repo_handler):
    print(f'Running base branch checker for {pr_handler.repo}#{pr_handler.number}')
    cl_config = repo_handler.get_config_value("basebranch_checker", {})
    basebranch = cl_config.get('basebranch', 'master')
    statuses = {}
    pr_basebranch = pr_handler.base_branch

    if pr_basebranch == basebranch:
        statuses['basebranch'] = {
            'description': f'PR opened correctly against {basebranch}',
            'state': 'success'}
    else:
        statuses['basebranch'] = {
            'description': f'PR opened against {pr_basebranch}, not {basebranch}',
            'state': 'failure'}

    return statuses
