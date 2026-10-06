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

# The mapping of repository full name to installation id is populated once at
# startup (by ``repo_to_installation_id_mapping``) and then kept up to date by
# the installation webhook handlers below, so that a GitHub API round-trip is
# not needed on every webhook delivery.
repo_to_installation_id_cache = {}
_repo_to_installation_id_populated = False


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

    The mapping is populated on first call (at startup) and then kept up to
    date by the ``add_installation`` / ``remove_installation`` family of
    helpers in response to installation webhook events.
    """
    global _repo_to_installation_id_populated
    if not _repo_to_installation_id_populated:
        for installation in get_integration().get_installations():
            for repo in installation.get_repos():
                repo_to_installation_id_cache[repo.full_name] = installation.id
        _repo_to_installation_id_populated = True
    return repo_to_installation_id_cache


def add_installation(installation_id):
    """
    Add all repositories belonging to an installation to the cache.

    Called when an installation is created or unsuspended.
    """
    installation_id = int(installation_id)
    installation = get_integration().get_app_installation(installation_id)
    for repo in installation.get_repos():
        repo_to_installation_id_cache[repo.full_name] = installation_id


def remove_installation(installation_id):
    """
    Remove all repositories belonging to an installation from the cache.

    Called when an installation is deleted or suspended.
    """
    installation_id = int(installation_id)
    for repo_name in list(repo_to_installation_id_cache):
        if repo_to_installation_id_cache[repo_name] == installation_id:
            del repo_to_installation_id_cache[repo_name]
    github_clients.pop(installation_id, None)
    installation_tokens.pop(installation_id, None)


def add_repositories_to_installation(installation_id, repositories):
    """
    Add repositories to the cache for a given installation.

    Called when repositories are added to an installation.
    """
    installation_id = int(installation_id)
    for repo_name in repositories:
        repo_to_installation_id_cache[repo_name] = installation_id


def remove_repositories_from_installation(repositories):
    """
    Remove repositories from the cache.

    Called when repositories are removed from an installation.
    """
    for repo_name in repositories:
        repo_to_installation_id_cache.pop(repo_name, None)


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
