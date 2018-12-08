from unittest.mock import patch, PropertyMock

from baldrick.github.github_api import cfg_cache
from baldrick.github.github_api import RepoHandler, PullRequestHandler
from baldrick.plugins.github_milestones import process_milestone, MISSING_MESSAGE, PRESENT_MESSAGE
from baldrick.plugins.github_team_updater import update_team_on_push

CONFIG_TEMPLATE = """
[ tool.testbot ]
[ tool.testbot.team_updater ]
enabled={enabled}
teams={teams}
"""

CONFIG_TEMPLATE_NOTEAMS = """
[ tool.testbot ]
[ tool.testbot.team_updater ]
enabled=true
"""

CONFIG_TEMPLATE_MISSING = """
[ tool.testbot ]
"""


class TestTeamUpdaterPlugin:

    def setup_method(self, method):

        self.get_file_contents_mock = patch('baldrick.github.github_api.RepoHandler.get_file_contents')
        self.get_file_contents = self.get_file_contents_mock.start()

        self.get_contributors_mock = patch('baldrick.github.github_api.RepoHandler.get_contributors')
        self.get_contributors = self.get_contributors_mock.start()

        self.get_teams_mock = patch('baldrick.github.github_api.OrganizationHandler.get_teams_mock')
        self.get_teams = self.get_teams_mock.start()

        self.get_members_mock = patch('baldrick.github.github_api.TeamHandler.get_members')
        self.get_members = self.get_members_mock.start()

        self.add_member_mock = patch('baldrick.github.github_api.TeamHandler.add_member')
        self.add_member = self.add_member_mock.start()

        self.repo_handler = RepoHandler("nota/repo")

        cfg_cache.clear()

    def teardown_method(self, method):
        self.get_file_contents_mock.stop()
        self.get_contributors_mock.stop()
        self.get_teams_mock.stop()
        self.get_members_mock.stop()
        self.add_member_mock.stop()

    def test_no_config(self, caplog):
        self.get_file_contents.return_value = CONFIG_TEMPLATE_MISSING
        update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert caplog.text == 'Skipping updating team since plugin is not enabled'

    def test_tag(self, caplog):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled=True, teams='aliens')
        update_team_on_push(self.repo_handler, 'refs/tags/v2.0')
        assert caplog.text == 'Skipping updating team since push was not to a branch'

    def test_disabled(self, caplog):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled=False, teams='')
        update_team_on_push(self.repo_handler, 'refs/tags/v2.0')
        assert caplog.text == 'Skipping updating team since plugin is not enabled'

    def test_no_teams(self, caplog):
        self.get_file_contents.return_value = CONFIG_TEMPLATE_NOTEAMS
        update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert caplog.text == 'Skipping updating team since no teams were specified'

    def test_empty_teams(self, caplog):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled=True, teams='')
        update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert caplog.text == 'Skipping updating team since no teams were specified'

    def test_add_single_member(self, caplog):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled=True, teams='humans')
        self.get_contributors.return_value = ['alice']
        self.get_teams.return_value = ['humans']
        self.get_members.return_value = []
        update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert caplog.text == 'Adding alice to humans'
        assert self.add_member.called_once_with('alice')

    def test_no_add_existing(self, caplog):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled=True, teams='humans')
        self.get_contributors.return_value = ['alice']
        self.get_teams.return_value = ['humans']
        self.get_members.return_value = ['alice']
        update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert self.add_member.call_count == 0

    def test_add_single_with_others_existing(self, caplog):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled=True, teams='humans')
        self.get_contributors.return_value = ['alice', 'bob']
        self.get_teams.return_value = ['humans']
        self.get_members.return_value = ['bob']
        update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert caplog.text == 'Adding alice to humans'
        assert self.add_member.called_once_with('alice')

    def test_add_to_multiple_teams(self, caplog):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled=True, teams='red,blue,green')
        self.get_contributors.return_value = ['alice', 'bob']
        self.get_teams.return_value = ['red', 'blue', 'green']
        self.get_members.return_value = ['bob']
        update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert caplog.text == 'Adding alice to red\nAdding alice to blue\nAdding alice to green'
        assert self.add_member.call_count == 3
