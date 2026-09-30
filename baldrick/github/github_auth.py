import netrc
import os

from github import Auth, GithubIntegration

# These are cached at the module level so that clients are reused between
# webhook deliveries. PyGithub refreshes the installation tokens used by the
# clients automatically when they are close to expiring.
# TODO: need to change global variable to use redis
integration = None
github_clients = {}


def netrc_exists():
    try:
        my_netrc = netrc.netrc()
    except FileNotFoundError:
        return False
    else:
        return my_netrc.authenticators("api.github.com") is not None


def get_integration():
    """
    Get a GithubIntegration authenticated as the GitHub App.
    """
    global integration

    if integration is None:
        # FIXME: if a .netrc file is present, the Authorization header will get
        # overwritten, so need to figure out how to ignore that file.
        if netrc_exists():
            raise Exception(
                "Authentication does not work properly if a ~/.netrc "
                "file exists. Rename that file temporarily and try again."
            )

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
