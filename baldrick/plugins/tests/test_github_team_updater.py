import logging

from unittest.mock import patch

from baldrick.github.github_api import cfg_cache
from baldrick.github.github_api import RepoHandler, TeamHandler
from baldrick.plugins.github_team_updater import update_team_on_push

CONFIG_TEMPLATE = """
[ tool.testbot ]
[ tool.testbot.team_updater ]
enabled = {enabled}
teams = "{teams}"
"""

CONFIG_TEMPLATE_NOTEAMS = """
[ tool.testbot ]
[ tool.testbot.team_updater ]
enabled = true
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

        self.get_teams_mock = patch('baldrick.github.github_api.OrganizationHandler.get_teams')
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

    def test_no_config(self, caplog, app):
        self.get_file_contents.return_value = CONFIG_TEMPLATE_MISSING
        with app.app_context():
            with caplog.at_level(logging.INFO):
                update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert len(caplog.records) == 1
        assert caplog.records[0].message == 'Skipping updating team since plugin is not enabled'

    def test_tag(self, caplog, app):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled='true', teams='aliens')
        print(self.get_file_contents())
        with app.app_context():
            with caplog.at_level(logging.INFO):
                update_team_on_push(self.repo_handler, 'refs/tags/v2.0')
        assert len(caplog.records) == 1
        assert caplog.records[0].message == 'Skipping updating team since push was not to a branch'

    def test_disabled(self, caplog, app):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled='false', teams='')
        with app.app_context():
            with caplog.at_level(logging.INFO):
                update_team_on_push(self.repo_handler, 'refs/heads/v2.0')
        assert len(caplog.records) == 1
        assert caplog.records[0].message == 'Skipping updating team since plugin is not enabled'

    def test_no_teams(self, caplog, app):
        self.get_file_contents.return_value = CONFIG_TEMPLATE_NOTEAMS
        with app.app_context():
            with caplog.at_level(logging.INFO):
                update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert len(caplog.records) == 1
        assert caplog.records[0].message == 'Skipping updating team since no teams were specified'

    def test_empty_teams(self, caplog, app):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled='true', teams='')
        with app.app_context():
            with caplog.at_level(logging.INFO):
                update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert len(caplog.records) == 1
        assert caplog.records[0].message == 'Skipping updating team since no teams were specified'

    def test_add_single_member(self, caplog, app):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled='true', teams='humans')
        self.get_contributors.return_value = ['alice']
        self.get_teams.return_value = [TeamHandler(123, name='humans')]
        self.get_members.return_value = []
        with app.app_context():
            with caplog.at_level(logging.INFO):
                update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert len(caplog.records) == 1
        assert caplog.records[0].message == 'Adding alice to humans'
        assert self.add_member.called_once_with('alice')

    def test_no_add_existing(self, caplog, app):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled='true', teams='humans')
        self.get_contributors.return_value = ['alice']
        self.get_teams.return_value = [TeamHandler(123, name='humans')]
        self.get_members.return_value = ['alice']
        with app.app_context():
            with caplog.at_level(logging.INFO):
                update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert self.add_member.call_count == 0
        assert len(caplog.records) == 0

    def test_add_single_with_others_existing(self, caplog, app):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled='true', teams='humans')
        self.get_contributors.return_value = ['alice', 'bob']
        self.get_teams.return_value = [TeamHandler(123, name='humans')]
        self.get_members.return_value = ['bob']
        with app.app_context():
            with caplog.at_level(logging.INFO):
                update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert len(caplog.records) == 1
        assert caplog.records[0].message == 'Adding alice to humans'
        assert self.add_member.called_once_with('alice')

    def test_add_to_multiple_teams(self, caplog, app):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled='true', teams='red,blue,green')
        self.get_contributors.return_value = ['alice', 'bob']
        self.get_teams.return_value = [TeamHandler(123, name='red'), TeamHandler(123, name='blue'), TeamHandler(123, name='green')]
        self.get_members.return_value = ['bob']
        with app.app_context():
            with caplog.at_level(logging.INFO):
                update_team_on_push(self.repo_handler, 'refs/heads/master')
        assert len(caplog.records) == 3
        assert caplog.records[0].message == 'Adding alice to red'
        assert caplog.records[1].message == 'Adding alice to blue'
        assert caplog.records[2].message == 'Adding alice to green'
        assert self.add_member.call_count == 3
