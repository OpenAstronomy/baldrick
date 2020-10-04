import sys
from unittest.mock import patch

import pytest

from baldrick.github.github_api import FILE_CACHE
from baldrick.github.github_api import RepoHandler, PullRequestHandler
from baldrick.plugins.github_towncrier_changelog import process_towncrier_changelog


CONFIG_TEMPLATE = """
[ tool.towncrier ]
    package = "testbot"
    filename = "NEWS.rst"

[ tool.testbot ]
[ tool.testbot.towncrier_changelog ]
enabled=true
"""

CUSTOM_TYPE_TEMPLATE = """
[tool.towncrier]
    package = "sunpy"
    directory = "changelog/"

    [[tool.towncrier.type]]
      directory = "doc"
      name = "Improved Documentation"
      showcontent = true

    [[tool.towncrier.type]]
      directory = "trivial"
      name = "Trivial/Internal Changes"
      showcontent = true

[ tool.testbot ]
[ tool.testbot.towncrier_changelog ]
enabled=true
"""


class TestTowncrierPlugin:

    def setup_method(self, method):

        self.get_file_contents_mock = patch('baldrick.github.github_api.PullRequestHandler.get_file_contents')
        self.get_base_branch_mock = patch('baldrick.github.github_api.PullRequestHandler.base_branch')
        a = self.get_base_branch_mock.start()
        a.return_value = "master"
        self.modified_files_mock = patch('baldrick.github.github_api.PullRequestHandler.get_modified_files')

        self.repo_handler = RepoHandler("nota/repo", "1234")
        self.pr_handler = PullRequestHandler("nota/repo", "1234")

        self.get_file_contents = self.get_file_contents_mock.start()
        self.modified_files = self.modified_files_mock.start()

        FILE_CACHE.clear()

    def teardown_method(self, method):
        self.get_file_contents_mock.stop()
        self.modified_files_mock.stop()
        self.get_base_branch_mock.stop()

    @pytest.mark.xfail(
        sys.platform.startswith('win'),
        reason='process_towncrier_changelog returns failure on Windows')
    def test_changelog_present(self, app):

        self.get_file_contents.return_value = CONFIG_TEMPLATE
        self.modified_files.return_value = (['./testbot/newsfragments/1234.bugfix'])

        with app.app_context():
            messages = process_towncrier_changelog(self.pr_handler, self.repo_handler)

        for message in messages.values():
            assert message['conclusion'] == 'success'

    @pytest.mark.xfail(
        sys.platform.startswith('win'),
        reason='process_towncrier_changelog returns failure on Windows')
    def test_changelog_type_substring(self, app):

        self.get_file_contents.return_value = CUSTOM_TYPE_TEMPLATE
        self.modified_files.return_value = (['changelog/1234.docfix.rst'])

        with app.app_context():
            messages = process_towncrier_changelog(self.pr_handler, self.repo_handler)

        assert messages['wrong_type']['conclusion'] == 'failure'
