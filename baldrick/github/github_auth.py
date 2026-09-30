import os

from cachetools import LRUCache
from github import Auth, GithubIntegration

# These are cached at the module level so that clients are reused between
# webhook deliveries. PyGithub refreshes the installation tokens used by the
# clients automatically when they are close to expiring.
integration = None
github_clients = LRUCache(maxsize=128)


def get_integration():
    """
    Get a GithubIntegration authenticated as the GitHub App.
    """
    global integration

    if integration is None:
        auth = Auth.AppAuth(os.environ["GITHUB_APP_INTEGRATION_ID"], os.environ["GITHUB_APP_PRIVATE_KEY"])

        # Use lazy clients so that constructing e.g. a Repository object does
        # not make an API call until actual data is needed from it.
        integration = GithubIntegration(auth=auth, lazy=True)

    return integration


def get_github(installation):
    """
    Get a Github client authenticated as the given installation.
    """
    installation = int(installation)

    if installation not in github_clients:
        github_clients[installation] = get_integration().get_github_for_installation(installation)

    return github_clients[installation]


def repo_to_installation_id_mapping():
    """
    Returns a dictionary mapping full repository name to installation id.
    """
    repos = {}
    for installation in get_integration().get_installations():
        for repo in installation.get_repos():
            repos[repo.full_name] = installation.id

    return repos
