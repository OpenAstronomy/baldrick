import pytest
from unittest.mock import patch, MagicMock

from baldrick.github.github_auth import (get_json_web_token, get_installation_token,
                                         github_request_headers, repo_to_installation_id_mapping,
                                         repo_to_installation_id, get_app_name)


def test_get_json_web_token(app):

    with app.app_context():

        # The first time we run this we should get a token
        token1 = get_json_web_token()

        # If we run it again immediately we should get the same token back
        token2 = get_json_web_token()

    assert token1 == token2


TOKEN_RESPONSE_VALID = {"token": "v1.1f699f1069f60xxx", "expires_at": "2016-07-11T22:14:10Z"}


def test_get_installation_token_valid():

    with patch('requests.post') as post:
        post.return_value.ok = True
        post.return_value.json.return_value = TOKEN_RESPONSE_VALID
        token = get_installation_token(12345)

    assert token == "v1.1f699f1069f60xxx"


TOKEN_RESPONSE_INVALID_WITH_MESSAGE = {"message": "This is the error message",
                                       "documentation_url": "https://developer.github.com/v3"}


def test_get_installation_token_invalid_with_message():

    with patch('requests.post') as post:
        post.return_value.ok = False
        post.return_value.json.return_value = TOKEN_RESPONSE_INVALID_WITH_MESSAGE
        with pytest.raises(Exception) as exc:
            get_installation_token(12345)
        assert exc.value.args[0] == TOKEN_RESPONSE_INVALID_WITH_MESSAGE['message']


TOKEN_RESPONSE_INVALID_WITHOUT_MESSAGE = {}


def test_get_installation_token_invalid_without_message():

    with patch('requests.post') as post:
        post.return_value.ok = False
        post.return_value.json.return_value = TOKEN_RESPONSE_INVALID_WITHOUT_MESSAGE
        with pytest.raises(Exception) as exc:
            get_installation_token(12345)
        assert exc.value.args[0] == "An error occurred when requesting token"


def test_github_request_headers():

    with patch('requests.post') as post:
        post.return_value.ok = True
        post.return_value.json.return_value = TOKEN_RESPONSE_VALID
        headers = github_request_headers(12345)

    assert headers['Authorization'] == 'token v1.1f699f1069f60xxx'


def requests_patch(url, headers=None):
    req = MagicMock()
    if url == 'https://api.github.com/app/installations':
        req.json.return_value = [{'id': 3331}]
    elif url == 'https://api.github.com/installation/repositories':
        req.json.return_value = {'repositories': [{'full_name': 'test1'},
                                                  {'full_name': 'test2'}]}
    return req


def test_repo_to_installation_id_mapping(app):

    with app.app_context():
        with patch('requests.post') as post:
            post.return_value.ok = True
            post.return_value.json.return_value = TOKEN_RESPONSE_VALID
            with patch('requests.get', requests_patch):
                mapping = repo_to_installation_id_mapping()

    assert mapping == {'test1': 3331, 'test2': 3331}


def test_repo_to_installation_id(app):

    with app.app_context():
        with patch('requests.post') as post:
            post.return_value.ok = True
            post.return_value.json.return_value = TOKEN_RESPONSE_VALID
            with patch('requests.get', requests_patch):

                assert repo_to_installation_id('test1') == 3331

                with pytest.raises(ValueError) as exc:
                    repo_to_installation_id('test3')
                assert exc.value.args[0] == 'Repository not recognized - should be one of:\n\n  - test1\n  - test2'


def test_get_app_name(app):

    with app.app_context():
        with patch('requests.get') as post:
            post.return_value.ok = True
            post.return_value.json.return_value = {'name': 'testbot'}
            name = get_app_name()

    assert name == 'testbot'
