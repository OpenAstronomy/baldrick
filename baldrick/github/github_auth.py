import os
import time
import netrc
import datetime
from collections import defaultdict, UserDict

import jwt
import requests
import dateutil.parser

TEN_MIN = datetime.timedelta(minutes=9)
ONE_MIN = datetime.timedelta(minutes=1)

# TODO: need to change global variable to use redis

json_web_token = None
json_web_token_expiry = None


def get_json_web_token():
    """
    Prepares the JSON Web Token (JWT) based on the private key.
    """

    global json_web_token
    global json_web_token_expiry

    now = datetime.datetime.now()

    # Include a one-minute buffer otherwise token might expire by the time we
    # make the request with the token.
    if json_web_token_expiry is None or now + ONE_MIN > json_web_token_expiry:

        json_web_token_expiry = now + TEN_MIN

        payload = {}

        # Issued at time
        payload['iat'] = int(now.timestamp())

        # JWT expiration time (10 minute maximum)
        payload['exp'] = int(json_web_token_expiry.timestamp())

        # Integration's GitHub identifier
        payload['iss'] = int(os.environ['GITHUB_APP_INTEGRATION_ID'])

        json_web_token = jwt.encode(payload,
                                    os.environ['GITHUB_APP_PRIVATE_KEY'].encode('ascii'),
                                    algorithm='RS256').decode('ascii')

    return json_web_token


installation_token = defaultdict(lambda: None)
installation_token_expiry = defaultdict(lambda: None)


def netrc_exists():
    try:
        my_netrc = netrc.netrc()
    except FileNotFoundError:
        return False
    else:
        return my_netrc.authenticators('api.github.com') is not None


def get_installation_token(installation):
    """
    Get access token for installation
    """

    now = datetime.datetime.now().timestamp()

    if installation_token_expiry[installation] is None or now + 60 > installation_token_expiry[installation]:

        # FIXME: if .netrc file is present, Authorization header will get
        # overwritten, so need to figure out how to ignore that file.
        if netrc_exists():
            raise Exception("Authentication does not work properly if a ~/.netrc "
                            "file exists. Rename that file temporarily and try again.")

        headers = {}
        headers['Authorization'] = 'Bearer {0}'.format(get_json_web_token())
        headers['Accept'] = 'application/vnd.github.machine-man-preview+json'

        url = 'https://api.github.com/installations/{0}/access_tokens'.format(installation)

        req = requests.post(url, headers=headers)
        resp = req.json()

        if not req.ok:
            if 'message' in resp:
                raise Exception(resp['message'])
            else:
                raise Exception("An error occurred when requesting token")

        installation_token[installation] = resp['token']
        installation_token_expiry[installation] = dateutil.parser.parse(resp['expires_at']).timestamp()

    return installation_token[installation]


def github_request_headers(installation):

    token = get_installation_token(installation)

    headers = {}
    headers['Authorization'] = 'token {0}'.format(token)
    headers['Accept'] = 'application/vnd.github.machine-man-preview+json'

    return headers


class InstallationCache(UserDict):
    """
    Retrieve and cache a repository : installation mapping.

    The objective of this class is to do the minimum amount of API calls to
    GitHub, while also having a way to respond to installations being
    uninstalled, and therefore removed from the cache.

    To get the repositories for an installation id is one API call per
    installation, while getting the list of installation ids is one API call.

    This class maintains a cache, which it will try and fetch installation ids
    from. The cache has a TTL, which when it expires the whole cache will be
    invalidated, as this is the only way to detect a repository being removed
    from an installation (as opposed to the installation being removed).

    When a key is requested from the cache, before refreshing the whole cache,
    a check is made for new installations as this is a cheaper operation than
    checking for new repositories in existing installations.

    Then we can use the username of the repository in the key to determine if
    we already have an installation for that user, and just refresh that user.
    """
    def __init__(self, ttl=48*60*60):
        self.ttl = ttl
        self._last_removal = time.time()
        self._install_ids = set()
        super().__init__()

    def clear_cache(self):
        """
        Clear the cache and fetch a whole new lot from GitHub.
        """
        self.data = {}
        self._last_removal = time.time()
        self._refresh_all_installations()

    def _update_install_ids(self):
        url = 'https://api.github.com/app/installations'
        headers = {}
        headers['Authorization'] = 'Bearer {0}'.format(get_json_web_token())
        headers['Accept'] = 'application/vnd.github.machine-man-preview+json'
        resp = requests.get(url, headers=headers)
        payload = resp.json()

        self._install_ids = {p['id'] for p in payload}

    # TODO: We could cache this function to prevent repeat refreshes in short time
    def _get_repos_for_id(self, iid):
        headers = github_request_headers(iid)
        resp = requests.get('https://api.github.com/installation/repositories', headers=headers)
        payload = resp.json()

        return [repo['full_name'] for repo in payload['repositories']]

    def _refresh_all_installations(self):
        self._update_install_ids()

        for iid in self._install_ids:
            repos = self._get_repos_for_id(iid)
            for repo in repos:
                self.data[repo] = iid

    def _add_new_installations_to_map(self):
        self._update_install_ids()

        mapped_ids = self.data.values()

        # Iterate over all the installation ids that are not in the map
        for iid in self._install_ids.difference(mapped_ids):
            repos = self._get_repos_for_id(iid)
            for repo in repos:
                self.data[repo] = iid

    def __getitem__(self, item):
        refreshed = (time.time() - self._last_removal) > self.ttl
        if refreshed:
            self.clear_cache()

        # First try with current cache, then check for new installations.
        try:
            return super().__getitem__(item)
        except KeyError:
            self._add_new_installations_to_map()

        # If not found in the new installations, we have to refresh the whole
        # lot in case someone added a new repo to an existing installation.
        try:
            return super().__getitem__(item)
        except KeyError:
            # If we have already blown away the cache, don't do it again.
            if not refreshed:
                self.clear_cache()  # TODO: This duplicates the work done above

        # Try now, and raise KeyError if the repo is still not found.
        return super().__getitem__(item)


def repo_to_installation_id_mapping():
    """
    Returns a dictionary mapping full repository name to installation id.
    """
    url = 'https://api.github.com/app/installations'
    headers = {}
    headers['Authorization'] = 'Bearer {0}'.format(get_json_web_token())
    headers['Accept'] = 'application/vnd.github.machine-man-preview+json'
    resp = requests.get(url, headers=headers)
    payload = resp.json()

    ids = [p['id'] for p in payload]

    repos = {}
    for iid in ids:
        headers = github_request_headers(iid)
        resp = requests.get('https://api.github.com/installation/repositories', headers=headers)
        payload = resp.json()
        for repo in payload['repositories']:
            repos[repo['full_name']] = iid

    return repos


def repo_to_installation_id(repository):
    """
    Return the installation ID for a repository.
    """
    mapping = repo_to_installation_id_mapping()
    if repository in mapping:
        return mapping[repository]
    else:
        raise ValueError("Repository not recognized - should be one of:\n\n  - " + "\n  - ".join(mapping))


def get_app_name():
    """
    Return the login name of the authenticated app.
    """
    headers = {}
    headers['Authorization'] = 'Bearer {0}'.format(get_json_web_token())
    headers['Accept'] = 'application/vnd.github.machine-man-preview+json'
    response = requests.get('https://api.github.com/app', headers=headers).json()
    return response['name']
