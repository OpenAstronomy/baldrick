import datetime
import netrc
import os

from github import Auth, GithubIntegration

# These are cached at the module level so that tokens and clients are reused
# between webhook deliveries. PyGithub refreshes the installation tokens
# used by the clients automatically when they are close to expiring.
# TODO: need to change global variable to use redis
integration = None
github_clients = {}
installation_tokens = {}


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
        integration = GithubIntegration(auth=auth)

    return integration


def get_github(installation):
    """
    Get a Github client authenticated as the given installation.
    """
    installation = int(installation)

    if installation not in github_clients:
        github_clients[installation] = get_integration().get_github_for_installation(installation)

    return github_clients[installation]


def get_installation_token(installation):
    """
    Get access token for installation
    """
    installation = int(installation)

    now = datetime.datetime.now(datetime.UTC)
    token = installation_tokens.get(installation)

    # Include a one-minute buffer otherwise the token might expire by the
    # time we make a request with it.
    if token is None or token.expires_at < now + datetime.timedelta(minutes=1):
        token = get_integration().get_access_token(installation)
        installation_tokens[installation] = token

    return token.token


def github_request_headers(installation):

    token = get_installation_token(installation)

    headers = {}
    headers["Authorization"] = f"token {token}"
    headers["Accept"] = "application/vnd.github+json"

    return headers


def repo_to_installation_id_mapping():
    """
    Returns a dictionary mapping full repository name to installation id.
    """
    repos = {}
    for installation in get_integration().get_installations():
        for repo in installation.get_repos():
            repos[repo.full_name] = installation.id

    return repos


def repo_to_installation_id(repository):
    """
    Return the installation ID for a repository.
    """
    mapping = repo_to_installation_id_mapping()
    if repository in mapping:
        return mapping[repository]
    raise ValueError("Repository not recognized - should be one of:\n\n  - " + "\n  - ".join(mapping))


def get_app_name():
    """
    Return the login name of the authenticated app.
    """
    return get_integration().get_app().name
