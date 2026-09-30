from unittest.mock import MagicMock, patch

import pytest

from baldrick.github import github_auth
from baldrick.github.github_auth import get_github, get_integration, repo_to_installation_id_mapping


@pytest.fixture(autouse=True)
def clear_auth_caches():
    github_auth.integration = None
    github_auth.github_clients.clear()


def test_get_integration(app):

    with app.app_context():
        # The integration should be able to mint an app JWT from the private
        # key, and the same integration should be returned on the second call.
        integration = get_integration()

    assert isinstance(integration.auth.create_jwt(), str)
    assert get_integration() is integration


def test_get_github_cached():

    with patch("baldrick.github.github_auth.get_integration") as integration:
        integration.return_value.get_github_for_installation.side_effect = lambda installation: MagicMock()

        client = get_github(12345)

        # The client should be reused for the same installation, including
        # when the installation is given as a string
        assert get_github(12345) is client
        assert get_github("12345") is client
        assert get_github(67890) is not client


def test_repo_to_installation_id_mapping():

    installation = MagicMock()
    installation.id = 3331
    installation.get_repos.return_value = []
    for full_name in ["test1", "test2"]:
        repo = MagicMock()
        repo.full_name = full_name
        installation.get_repos.return_value.append(repo)

    with patch("baldrick.github.github_auth.get_integration") as integration:
        integration.return_value.get_installations.return_value = [installation]
        mapping = repo_to_installation_id_mapping()

    assert mapping == {"test1": 3331, "test2": 3331}
