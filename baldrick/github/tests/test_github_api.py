import base64

from unittest.mock import patch, Mock, PropertyMock, MagicMock

import pytest

from baldrick.config import loads
from baldrick.github.github_api import (FILE_CACHE, RepoHandler, IssueHandler,
                                        PullRequestHandler)


# TODO: Add more tests to increase coverage.

class TestRepoHandler:

    def setup_class(self):
        self.repo = RepoHandler('fakerepo/doesnotexist', branch='awesomebot')

    @patch('requests.get')
    def test_get_issues(self, mock_get):
        # http://engineroom.trackmaven.com/blog/real-life-mocking/
        mock_response = Mock()
        mock_response.json.return_value = [
            {'number': 42, 'state': 'open'},
            {'number': 55, 'state': 'open',
             'pull_request': {'diff_url': 'blah'}}]
        mock_get.return_value = mock_response

        assert self.repo.get_issues('open', 'Close?') == [42]
        assert self.repo.get_issues('open', 'Close?',
                                    exclude_pr=False) == [42, 55]

    @patch('requests.get')
    def test_get_all_labels(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = [
            {'name': 'io.fits'},
            {'name': 'Documentation'}]
        mock_response.headers = {}
        mock_get.return_value = mock_response

        assert self.repo.get_all_labels() == ['io.fits', 'Documentation']

    def test_urls(self):
        assert self.repo._url_contents == 'https://api.github.com/repos/fakerepo/doesnotexist/contents/'
        assert self.repo._url_pull_requests == 'https://api.github.com/repos/fakerepo/doesnotexist/pulls'
        assert self.repo._headers == {}


TEST_CONFIG = """
[tool.testbot]
[tool.testbot.pr]
setting1 = 2
setting2 = 3
"""


TEST_GLOBAL_CONFIG = """
[tool.testbot]
[tool.testbot.pr]
setting1 = 1
setting2 = 5
setting3 = 6
[tool.testbot.other]
setting4 = 5
"""


TEST_FALLBACK_CONFIG = """
[tool.nottestbot]
[tool.nottestbot.pr]
setting1 = 5
setting3 = 4
"""


class TestRealRepoHandler:

    def setup_method(self, method):
        FILE_CACHE.clear()

    def setup_class(self):
        self.repo = RepoHandler('astropy/astropy-bot')

    def test_get_config(self, app):

        with app.app_context():

            with patch.object(self.repo, 'get_file_contents') as mock_get:  # noqa

                mock_get.return_value = TEST_CONFIG

                # These are set to False in YAML; defaults must not be used.
                assert self.repo.get_config_value('pr')['setting1'] == 2
                assert self.repo.get_config_value('pr')['setting2'] == 3

    def test_get_fallback_config(self, app):

        with app.app_context():
            app.fall_back_config = "nottestbot"
            with patch.object(self.repo, 'get_file_contents') as mock_get:  # noqa

                mock_get.return_value = TEST_FALLBACK_CONFIG

                # These are set to False in YAML; defaults must not be used.
                assert self.repo.get_config_value('pr')['setting1'] == 5
                assert self.repo.get_config_value('pr')['setting3'] == 4

    def test_get_fallback_with_primary_config(self, app):

        with app.app_context():
            app.fall_back_config = "nottestbot"
            with patch.object(self.repo, 'get_file_contents') as mock_get:  # noqa

                mock_get.return_value = TEST_CONFIG + TEST_FALLBACK_CONFIG

                # These are set to False in YAML; defaults must not be used.
                assert self.repo.get_config_value('pr')['setting1'] == 2
                assert self.repo.get_config_value('pr')['setting2'] == 3
                assert self.repo.get_config_value('pr')['setting3'] == 4

    def test_get_config_with_app_defaults(self, app):

        with app.app_context():

            with patch.object(self.repo, 'get_file_contents') as mock_get:  # noqa

                mock_get.return_value = TEST_CONFIG

                # These are set to False in YAML; defaults must not be used.
                assert self.repo.get_config_value('pr') == {'setting1': 2, 'setting2': 3}
                assert self.repo.get_config_value('other') is None

                app.conf = loads(TEST_GLOBAL_CONFIG, tool='testbot')

                assert self.repo.get_config_value('pr') == {'setting1': 2, 'setting2': 3, 'setting3': 6}
                assert self.repo.get_config_value('other') == {'setting4': 5}

    @patch('requests.get')
    def test_get_file_contents(self, mock_get):
        content = b"I, for one, welcome our new robot overlords"

        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {'content': base64.b64encode(content)}
        mock_get.return_value = mock_response

        result = self.repo.get_file_contents('some/file/here.txt')
        assert result == content.decode('utf-8')

    @patch('requests.get')
    def test_missing_file_contents(self, mock_get):
        mock_response = Mock()
        mock_response.ok = False
        mock_response.json.return_value = {'message': 'Not Found'}
        mock_get.return_value = mock_response

        with pytest.raises(FileNotFoundError):
            self.repo.get_file_contents('some/file/here.txt')


class TestIssueHandler:
    def setup_class(self):
        self.issue = IssueHandler('fakerepo/doesnotexist', 1234)

    def test_urls(self):
        assert self.issue._url_issue == 'https://api.github.com/repos/fakerepo/doesnotexist/issues/1234'
        assert self.issue._url_issue_nonapi == 'https://github.com/fakerepo/doesnotexist/issues/1234'
        assert self.issue._url_labels == 'https://api.github.com/repos/fakerepo/doesnotexist/issues/1234/labels'
        assert self.issue._url_issue_comment == 'https://api.github.com/repos/fakerepo/doesnotexist/issues/1234/comments'
        assert self.issue._url_timeline == 'https://api.github.com/repos/fakerepo/doesnotexist/issues/1234/timeline'

    @pytest.mark.parametrize(('state', 'answer'),
                             [('open', False), ('closed', True)])
    def test_is_closed(self, state, answer):
        with patch('baldrick.github.github_api.IssueHandler.json', new_callable=PropertyMock) as mock_json:  # noqa
            mock_json.return_value = {'state': state}
            assert self.issue.is_closed is answer

    def test_missing_labels(self):
        with patch('baldrick.github.github_api.IssueHandler.labels', new_callable=PropertyMock) as mock_issue_labels:  # noqa
            mock_issue_labels.return_value = ['io.fits']
            with patch('baldrick.github.github_api.RepoHandler.get_all_labels') as mock_repo_labels:  # noqa
                mock_repo_labels.return_value = ['io.fits', 'closed-by-bot']

                # closed-by-bot label will be added to issue in POST
                missing_labels = self.issue._get_missing_labels('closed-by-bot')
                assert missing_labels == ['closed-by-bot']

                # Desired labels do not exist in repo
                missing_labels = self.issue._get_missing_labels(
                    ['dummy', 'foo'])
                assert missing_labels is None

                # Desired label already set on issue
                missing_labels = self.issue._get_missing_labels(['io.fits'])
                assert missing_labels is None

                # A mix
                missing_labels = self.issue._get_missing_labels(
                    ['io.fits', 'closed-by-bot', 'foo'])
                assert missing_labels == ['closed-by-bot']


class TestPullRequestHandler:
    def setup_class(self):
        self.pr = PullRequestHandler('fakerepo/doesnotexist', 1234)

    def test_urls(self):
        assert self.pr._url_pull_request == 'https://api.github.com/repos/fakerepo/doesnotexist/pulls/1234'
        assert self.pr._url_review_comment == 'https://api.github.com/repos/fakerepo/doesnotexist/pulls/1234/reviews'
        assert self.pr._url_commits == 'https://api.github.com/repos/fakerepo/doesnotexist/pulls/1234/commits'
        assert self.pr._url_files == 'https://api.github.com/repos/fakerepo/doesnotexist/pulls/1234/files'

    def test_has_modified(self):
        mock = MagicMock(return_value=[{
            "sha": "bbcd538c8e72b8c175046e27cc8f907076331401",
            "filename": "file1.txt",
            "status": "added",
            "additions": 103,
            "deletions": 21,
            "changes": 124,
            "blob_url": "https://github.com/blah/blah/blob/hash/file1.txt",
            "raw_url": "https://github.com/blaht/blah/raw/hash/file1.txt",
            "contents_url": "https://api.github.com/repos/blah/blah/contents/file1.txt?ref=hash",
            "patch": "@@ -132,7 +132,7 @@ module Test @@ -1000,7 +1000,7 @@ module Test"
        }])
        with patch('baldrick.github.github_api.paged_github_json_request', mock):  # noqa
            assert self.pr.has_modified(['file1.txt'])
            assert self.pr.has_modified(['file1.txt', 'notthis.txt'])
            assert not self.pr.has_modified(['notthis.txt'])


    def test_set_check(self, app):
        with patch("baldrick.github.github_api.PullRequestHandler.json", new_callable=PropertyMock) as json:
            json.return_value = {'head': {'sha': 987654321},
                                 'base': {'sha': 123456789}}
            with patch('requests.post') as post:
                self.pr.set_check("baldrick-1", "hello", name="test")
                expected_json = {'external_id': 'baldrick-1',
                                 'name': 'test',
                                 'head_sha': 987654321,
                                 'status': 'completed',
                                 'output': {'title': 'hello', 'summary': ''},
                                 'conclusion': 'neutral'}
                post.assert_called_once_with('https://api.github.com/repos/fakerepo/doesnotexist/check-runs',
                                             headers={'Accept': 'application/vnd.github.antiope-preview+json'},
                                             json=expected_json)

                post.reset_mock()

                self.pr.set_check("baldrick-1", "hello", name="test",
                                  commit_hash='base', text="hello world", summary="why hello")
                expected_json = {'external_id': 'baldrick-1',
                                 'name': 'test',
                                 'head_sha': 123456789,
                                 'status': 'completed',
                                 'output': {'title': 'hello', 'summary': 'why hello', 'text': 'hello world'},
                                 'conclusion': 'neutral'}
                post.assert_called_once_with('https://api.github.com/repos/fakerepo/doesnotexist/check-runs',
                                             headers={'Accept': 'application/vnd.github.antiope-preview+json'},
                                             json=expected_json)

                post.reset_mock()

                self.pr.set_check("baldrick-1", "hello", name="test",
                                  commit_hash='hello', details_url="this_is_a_url")
                expected_json = {'external_id': 'baldrick-1',
                                 'name': 'test',
                                 'head_sha': 'hello',
                                 'details_url': 'this_is_a_url',
                                 'status': 'completed',
                                 'output': {'title': 'hello', 'summary': ''},
                                 'conclusion': 'neutral'}
                post.assert_called_once_with('https://api.github.com/repos/fakerepo/doesnotexist/check-runs',
                                             headers={'Accept': 'application/vnd.github.antiope-preview+json'},
                                             json=expected_json)

                post.reset_mock()

                self.pr.set_check("baldrick-1", "hello", name="test",
                                  status="completed", conclusion=None)
                expected_json = {'external_id': 'baldrick-1',
                                 'name': 'test',
                                 'head_sha': 987654321,
                                 'status': 'completed',
                                 'output': {'title': 'hello', 'summary': ''},
                                 'conclusion': 'neutral'}
                post.assert_called_once_with('https://api.github.com/repos/fakerepo/doesnotexist/check-runs',
                                             headers={'Accept': 'application/vnd.github.antiope-preview+json'},
                                             json=expected_json)
