from unittest.mock import patch, PropertyMock

from baldrick.github.github_api import cfg_cache
from baldrick.github.github_api import RepoHandler, PullRequestHandler
from baldrick.plugins.github_milestones import process_milestone, MISSING_MESSAGE, PRESENT_MESSAGE


CONFIG_TEMPLATE = """
[ tool.testbot ]
[ tool.testbot.milestones ]
enabled=true
missing_message="{missing}"
present_message="{present}"
"""

CONFIG_TEMPLATE_DEFAULT = """
[ tool.testbot ]
[ tool.testbot.milestones ]
enabled=true
"""

CONFIG_TEMPLATE_MISSING = """
[ tool.testbot ]
"""


class TestMilestonePlugin:

    def setup_method(self, method):

        self.get_file_contents_mock = patch('baldrick.github.github_api.PullRequestHandler.get_file_contents')
        self.get_base_branch_mock = patch('baldrick.github.github_api.PullRequestHandler.base_branch')
        a = self.get_base_branch_mock.start()
        a.return_value = "master"
        self.milestone_mock = patch('baldrick.github.github_api.PullRequestHandler.milestone',
                                    new_callable=PropertyMock)

        self.repo_handler = RepoHandler("nota/repo", "1234")
        self.pr_handler = PullRequestHandler("nota/repo", "1234")

        self.milestone = self.milestone_mock.start()
        self.milestone.return_value = None

        self.get_file_contents = self.get_file_contents_mock.start()
        cfg_cache.clear()

    def teardown_method(self, method):
        self.get_file_contents_mock.stop()
        self.milestone_mock.stop()
        self.get_base_branch_mock.stop()

    def test_milestone_present(self, app):

        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(missing="missing milestone",
                                                                     present="milestone present")
        self.milestone.return_value = "0.1"

        with app.app_context():
            ret = process_milestone(self.pr_handler, self.repo_handler)

        assert "milestone" in ret
        assert len(ret) == 1
        assert ret['milestone']['state'] == "success"
        assert ret['milestone']['description'] == "milestone present"

    def test_milestone_absent(self, app):

        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(missing="missing milestone",
                                                                     present="milestone present")
        with app.app_context():
            ret = process_milestone(self.pr_handler, self.repo_handler)

        assert "milestone" in ret
        assert len(ret) == 1
        assert ret['milestone']['state'] == "failure"
        assert ret['milestone']['description'] == "missing milestone"

    def test_milestone_present_default(self, app):

        self.get_file_contents.return_value = CONFIG_TEMPLATE_DEFAULT
        self.milestone.return_value = "0.1"

        with app.app_context():
            ret = process_milestone(self.pr_handler, self.repo_handler)

        assert "milestone" in ret
        assert len(ret) == 1
        assert ret['milestone']['state'] == "success"
        assert ret['milestone']['description'] == PRESENT_MESSAGE

    def test_milestone_absent_default(self, app):

        self.get_file_contents.return_value = CONFIG_TEMPLATE_DEFAULT
        with app.app_context():
            ret = process_milestone(self.pr_handler, self.repo_handler)

        assert "milestone" in ret
        assert len(ret) == 1
        assert ret['milestone']['state'] == "failure"
        assert ret['milestone']['description'] == MISSING_MESSAGE

    def test_no_config(self, app):
        self.get_file_contents.return_value = CONFIG_TEMPLATE_MISSING
        with app.app_context():
            ret = process_milestone(self.pr_handler, self.repo_handler)

        assert ret is None
