# A plugin that can automatically update a team based on contributors to a
# repository.

import logging

from baldrick.plugins.github_pushes import push_handler

LOGGER = logging.getLogger(__name__)


@push_handler
def update_team_on_push(repo_handler, git_ref):

    # Get configuration for this plugin
    config = repo_handler.get_config_value("team_updater", {})
    if not config.get('enabled', False):
        LOGGER.info('Skipping updating team since plugin is not enabled')
        return

    # Only update team when pushing to a branch (not e.g. a tag)
    if not git_ref.startswith('refs/heads/'):
        LOGGER.info('Skipping updating team since push was not to a branch')
        return

    # Find out teams to add contributors to
    teams = config.get('teams', None)
    if teams is None:
        LOGGER.info('Skipping updating team since no teams were specified')
        return
    else:
        teams = teams.split(',')

    # Get a list of contributors to the repository
    contributors = repo_handler.get_contributors()

    # Find the organization the repository is part of
    organization = repo_handler.get_organization()

    for team_name in teams:

        # Get a reference to the team
        team = organization.get_team_by_name(team_name)

        # Find all members of the team
        members = team.get_members()

        # Find all contributors not yet in the team
        missing = set(contributors) - set(members)

        # Add these contributors to the team
        for member in missing:
            LOGGER.info(f'Adding {member} to {team_name}')
            team.add_member(member)
