from unittest.mock import MagicMock, patch

import pytest

from baldrick.conftest import PRIVATE_KEY
from baldrick.github.github_auth import GithubAppAuth


TOKEN_RESPONSE_INVALID_WITH_MESSAGE = {
    "message": "This is the error message",
    "documentation_url": "https://developer.github.com/v3",
}

TOKEN_RESPONSE_INVALID_WITHOUT_MESSAGE = {}


def test_json_web_token(auth):

    # The first time we run this we should get a token
    token1 = auth.json_web_token

    # If we run it again immediately we should get the same token back
    token2 = auth.json_web_token

    assert token1 == token2


def test_get_installation_token_valid(auth):

    with patch("requests.post") as post:
        post.return_value.ok = True
        post.return_value.json.return_value = TOKEN_RESPONSE_VALID
        token = auth.get_installation_token(12345)

    assert token == "v1.1f699f1069f60xxx"


def test_get_installation_token_invalid_with_message(auth):

    with patch("requests.post") as post:
        post.return_value.ok = False
        post.return_value.status_code = 400
        post.return_value.json.return_value = TOKEN_RESPONSE_INVALID_WITH_MESSAGE
        with pytest.raises(Exception, match="400 This is the error message") as exc:
            auth.get_installation_token(12345)
        assert exc.value.args[0] == f"{post.return_value.status_code} {TOKEN_RESPONSE_INVALID_WITH_MESSAGE['message']}"


def test_get_installation_token_invalid_without_message(auth):

    with patch("requests.post") as post:
        post.return_value.ok = False
        post.return_value.json.return_value = TOKEN_RESPONSE_INVALID_WITHOUT_MESSAGE
        with pytest.raises(Exception, match="An error occurred when requesting token") as exc:
            auth.get_installation_token(12345)
        assert exc.value.args[0] == "An error occurred when requesting token"


def test_get_github_request_headers(auth):

    with patch("requests.post") as post:
        post.return_value.ok = True
        post.return_value.json.return_value = TOKEN_RESPONSE_VALID
        headers = auth.get_github_request_headers(12345)

    assert headers["Authorization"] == "token v1.1f699f1069f60xxx"


def test_repo_to_installation_id_mapping(auth):

    assert auth.repo_to_installation_id_mapping == {"test1": 3331, "test2": 3331}


def test_repo_to_installation_id(auth):

    assert auth.repo_to_installation_id("test1") == 3331

    with pytest.raises(ValueError, match="Repository not recognized"):
        auth.repo_to_installation_id("test3")


def test_app_name(auth):

    assert auth.app_name == "testbot"


def test_add_and_remove_repo_to_installations(auth):

    auth.add_repo_to_installations("test3", 3331)
    assert auth.repo_to_installation_id("test3") == 3331

    auth.remove_repo_from_installations("test3")
    with pytest.raises(ValueError, match="Repository not recognized"):
        auth.repo_to_installation_id("test3")
