import datetime
from unittest.mock import MagicMock, patch

import pytest

from baldrick.github import github_auth
from baldrick.github.github_auth import (
    add_installation,
    add_repositories_to_installation,
    get_app_name,
    get_installation_token,
    get_integration,
    github_request_headers,
    remove_installation,
    remove_repositories_from_installation,
    repo_to_installation_id,
    repo_to_installation_id_mapping,
)


@pytest.fixture(autouse=True)
def clear_auth_caches():
    github_auth.integration = None
    github_auth.github_clients.clear()
    github_auth.installation_tokens.clear()
    github_auth.repo_to_installation_id_cache.clear()
    github_auth._repo_to_installation_id_populated = False


def make_token(token, minutes=10):
    access_token = MagicMock()
    access_token.token = token
    access_token.expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=minutes)
    return access_token


def test_get_integration(app):

    with app.app_context():
        # The integration should be able to mint an app JWT from the private
        # key, and the same integration should be returned on the second call.
        integration = get_integration()

    assert isinstance(integration.auth.create_jwt(), str)
    assert get_integration() is integration


def test_get_installation_token():

    with patch("baldrick.github.github_auth.get_integration") as integration:
        integration.return_value.get_access_token.return_value = make_token("v1.1f699f1069f60xxx")
        token = get_installation_token(12345)

    assert token == "v1.1f699f1069f60xxx"


def test_get_installation_token_cached():

    with patch("baldrick.github.github_auth.get_integration") as integration:
        integration.return_value.get_access_token.return_value = make_token("token1")
        assert get_installation_token(12345) == "token1"

        # The first token is still valid, so it should be reused
        integration.return_value.get_access_token.return_value = make_token("token2")
        assert get_installation_token(12345) == "token1"


def test_get_installation_token_expired():

    with patch("baldrick.github.github_auth.get_integration") as integration:
        integration.return_value.get_access_token.return_value = make_token("token1", minutes=0)
        assert get_installation_token(12345) == "token1"

        # The first token is about to expire, so a new one should be requested
        integration.return_value.get_access_token.return_value = make_token("token2")
        assert get_installation_token(12345) == "token2"


def test_github_request_headers():

    with patch("baldrick.github.github_auth.get_integration") as integration:
        integration.return_value.get_access_token.return_value = make_token("v1.1f699f1069f60xxx")
        headers = github_request_headers(12345)

    assert headers["Authorization"] == "token v1.1f699f1069f60xxx"


def make_installation(installation_id, repositories):
    installation = MagicMock()
    installation.id = installation_id
    installation.get_repos.return_value = []
    for full_name in repositories:
        repo = MagicMock()
        repo.full_name = full_name
        installation.get_repos.return_value.append(repo)
    return installation


def test_repo_to_installation_id_mapping():

    with patch("baldrick.github.github_auth.get_integration") as integration:
        integration.return_value.get_installations.return_value = [make_installation(3331, ["test1", "test2"])]
        mapping = repo_to_installation_id_mapping()

    assert mapping == {"test1": 3331, "test2": 3331}


def test_repo_to_installation_id_mapping_cached():

    with patch("baldrick.github.github_auth.get_integration") as integration:
        integration.return_value.get_installations.return_value = [make_installation(3331, ["test1", "test2"])]
        repo_to_installation_id_mapping()

        # On the second call the API should not be consulted again.
        integration.return_value.get_installations.return_value = []
        mapping = repo_to_installation_id_mapping()

    assert mapping == {"test1": 3331, "test2": 3331}


def test_add_installation():

    with patch("baldrick.github.github_auth.get_integration") as integration:
        integration.return_value.get_app_installation.return_value = make_installation(99, ["a/b", "c/d"])
        add_installation(99)

    assert github_auth.repo_to_installation_id_cache == {"a/b": 99, "c/d": 99}


def test_add_installation_existing_repos_replaced():

    github_auth.repo_to_installation_id_cache["a/b"] = 1
    github_auth._repo_to_installation_id_populated = True

    with patch("baldrick.github.github_auth.get_integration") as integration:
        integration.return_value.get_app_installation.return_value = make_installation(99, ["a/b", "c/d"])
        add_installation(99)

    assert github_auth.repo_to_installation_id_cache == {"a/b": 99, "c/d": 99}


def test_remove_installation():

    github_auth.repo_to_installation_id_cache.update({"a/b": 99, "c/d": 99, "e/f": 1})
    github_auth._repo_to_installation_id_populated = True

    remove_installation(99)

    assert github_auth.repo_to_installation_id_cache == {"e/f": 1}


def test_remove_installation_clears_clients_and_tokens():

    github_auth.github_clients[99] = MagicMock()
    github_auth.installation_tokens[99] = "tok"

    remove_installation(99)

    assert 99 not in github_auth.github_clients
    assert 99 not in github_auth.installation_tokens


def test_add_repositories_to_installation():

    github_auth._repo_to_installation_id_populated = True

    add_repositories_to_installation(42, ["a/b", "c/d"])

    assert github_auth.repo_to_installation_id_cache == {"a/b": 42, "c/d": 42}


def test_remove_repositories_from_installation():

    github_auth.repo_to_installation_id_cache.update({"a/b": 42, "c/d": 42, "e/f": 1})
    github_auth._repo_to_installation_id_populated = True

    remove_repositories_from_installation(["a/b", "c/d"])

    assert github_auth.repo_to_installation_id_cache == {"e/f": 1}


def test_repo_to_installation_id():

    with patch("baldrick.github.github_auth.get_integration") as integration:
        integration.return_value.get_installations.return_value = [make_installation(3331, ["test1", "test2"])]

        assert repo_to_installation_id("test1") == 3331

        with pytest.raises(ValueError, match="Repository not recognized") as exc:
            repo_to_installation_id("test3")
        assert exc.value.args[0] == "Repository not recognized - should be one of:\n\n  - test1\n  - test2"


def test_get_app_name():

    with patch("baldrick.github.github_auth.get_integration") as integration:
        integration.return_value.get_app.return_value.name = "testbot"
        assert get_app_name() == "testbot"
