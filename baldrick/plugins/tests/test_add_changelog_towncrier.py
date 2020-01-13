import json
from pathlib import Path
from unittest.mock import patch, PropertyMock

from baldrick.github.github_api import FILE_CACHE
from baldrick.github.github_api import RepoHandler, PullRequestHandler
from baldrick.plugins.github_comment_matcher import handle_issue_comments
from baldrick.plugins.towncrier_add_entry import add_changelog_entry


CONFIG_TEMPLATE = """
[ tool.testbot ]
[ tool.testbot.issue_comments ]
enabled=true
"""


class TestAddChangelogPlugin:

    def setup_method(self, method):

        self.get_file_contents_mock = patch('baldrick.github.github_api.PullRequestHandler.get_file_contents')
        self.get_base_branch_mock = patch('baldrick.github.github_api.PullRequestHandler.base_branch')
        a = self.get_base_branch_mock.start()
        a.return_value = "master"

        self.repo_handler = RepoHandler("nota/repo", "1234")
        self.pr_handler = PullRequestHandler("nota/repo", "1234")

        self.get_file_contents = self.get_file_contents_mock.start()
        FILE_CACHE.clear()

    def teardown_method(self, method):
        self.get_file_contents_mock.stop()
        self.get_base_branch_mock.stop()

    @property
    def issue_comment_payload(self):
        with open(Path(__file__).parent / 'issue_comment_payload.json') as fobj:
            return json.loads(fobj.read())

    def test_handle_issue_comments(self, app):
        handle_issue_comments(self.repo_handler, self.issue_comment_payload,
                              {'X-GitHub-Event': 'issue_comment'})

    def test_milestone_present(self, app):

        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(missing="missing milestone",
                                                                     present="milestone present")
        with app.app_context():
            ret = add_changelog_entry(self.pr_handler, self.repo_handler, "hello", None)

