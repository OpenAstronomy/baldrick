import datetime
import netrc
import time

import dateutil.parser
import jwt
import requests
from cachetools import TTLCache, TLRUCache
from loguru import logger

NINE_MIN = datetime.timedelta(minutes=9)


__all__ = ["GithubAppAuth"]


def netrc_exists():
    try:
        my_netrc = netrc.netrc()
    except FileNotFoundError:
        return False
    else:
        return my_netrc.authenticators("api.github.com") is not None


class GithubAppAuth:
    """
    A Class for managing multiple github app installations and tokens.
    """

    def __init__(self, app_integration_id, app_private_key, *, jwt_cache_ttl=NINE_MIN.seconds):
        self.app_integration_id = app_integration_id
        self.app_private_key = app_private_key

        # GitHub expires the token after 10 mins so cache for 9.
        self._jwt_cache = TTLCache(maxsize=1, ttl=jwt_cache_ttl)
        self._installation_token_cache = TLRUCache(maxsize=512, ttu=self._token_ttu, timer=time.time)

        # Validate are a authenticated as a GitHub App
        app_info = self.app_info
        logger.info(f"Authenticated as {app_info['name']} with {app_info.get('installations_count')} installations.")

        # Populate repo installation mapping
        self._repo_installation_mapping = {}
        self._populate_repo_to_installation_id_mapping()

    @property
    def json_web_token(self):
        """
        Prepares the JSON Web Token (JWT) based on the private key.
        """

        # Ensure we expire any out of date tokens, TTLCache only expires on mutation.
        self._jwt_cache.expire()

        json_web_token = self._jwt_cache.get("jwt")

        # Include a one-minute buffer otherwise token might expire by the time we
        # make the request with the token.
        if json_web_token is None:
            now = datetime.datetime.now()

            payload = {}

            # Issued at time
            payload["iat"] = int(now.timestamp())

            # JWT expiration time (10 minute maximum)
            payload["exp"] = int((now + NINE_MIN).timestamp())

            # Integration's GitHub identifier
            payload["iss"] = self.app_integration_id

            json_web_token = jwt.encode(payload, self.app_private_key, algorithm="RS256")
            self._jwt_cache["jwt"] = json_web_token

        return json_web_token

    @property
    def app_info(self):
        """
        Return the information about this app.
        """
        headers = {}
        headers["Authorization"] = f"Bearer {self.json_web_token}"
        headers["Accept"] = "application/vnd.github.machine-man-preview+json"
        response = requests.get("https://api.github.com/app", headers=headers)

        response.raise_for_status()

        return response.json()

    @property
    def app_name(self):
        """
        Return the app name
        """
        return self.app_info["name"]

    @staticmethod
    def _token_ttu(key, value, now):
        return value["expires_at"]

    def get_installation_token(self, installation):
        """
        Get access token for installation
        """
        # FIXME: if .netrc file is present, Authorization header will get
        # overwritten, so need to figure out how to ignore that file.
        if netrc_exists():
            raise Exception(
                "Authentication does not work properly if a ~/.netrc "
                "file exists. Rename that file temporarily and try again."
            )

        # Ensure we expire any out of date tokens, TTLUCache only expires on mutation.
        self._installation_token_cache.expire()

        installation_token = self._installation_token_cache.get(installation)

        if installation_token is None:
            installation_token = {}

            headers = {}
            headers["Authorization"] = f"Bearer {self.json_web_token}"
            headers["Accept"] = "application/vnd.github+json"
            headers["X-GitHub-Api-Version"] = "2022-11-28"

            url = f"https://api.github.com/app/installations/{installation}/access_tokens"

            req = requests.post(url, headers=headers)
            resp = req.json()

            if not req.ok:
                if "message" in resp:
                    raise Exception(f"{req.status_code} {resp['message']}")
                raise Exception("An error occurred when requesting token")

            installation_token["token"] = resp["token"]
            installation_token["expires_at"] = dateutil.parser.parse(resp["expires_at"]).timestamp()
            self._installation_token_cache[installation] = installation_token

        return installation_token["token"]

    def get_github_request_headers(self, installation):
        token = self.get_installation_token(installation)

        headers = {}
        headers["Authorization"] = f"token {token}"
        headers["Accept"] = "application/vnd.github.machine-man-preview+json"

        return headers

    def add_repo_to_installations(self, repo, installation):
        """
        Inserts an installation in the repo mapping.
        """
        self._repo_installation_mapping[repo] = installation

    def remove_repo_from_installations(self, repo):
        """
        Inserts an installation in the repo mapping.
        """
        del self._repo_installation_mapping[repo]

    def _get_installation_ids(self):
        url = "https://api.github.com/app/installations"
        headers = {}
        headers["Authorization"] = f"Bearer {self.json_web_token}"
        headers["Accept"] = "application/vnd.github+json"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
        resp = requests.get(url, headers=headers)
        payload = resp.json()

        if resp.status_code != 200:
            raise ValueError(f"{resp.status_code} {payload} in response from GitHub while getting installations")

        return [p["id"] for p in payload]

    def _populate_repo_to_installation_id_mapping(self):
        ids = self._get_installation_ids()

        for iid in ids:
            headers = self.get_github_request_headers(iid)
            resp = requests.get("https://api.github.com/installation/repositories", headers=headers)
            payload = resp.json()
            for repo in payload["repositories"]:
                self._repo_installation_mapping[repo["full_name"]] = iid

    @property
    def repo_to_installation_id_mapping(self):
        """
        Returns a dictionary mapping full repository name to installation id.
        """
        return self._repo_installation_mapping

    def repo_to_installation_id(self, repository):
        """
        Return the installation ID for a repository.
        """
        install_id = self.repo_to_installation_id_mapping.get(repository)
        if install_id is None:
            raise ValueError("Repository not recognized")
        return install_id
