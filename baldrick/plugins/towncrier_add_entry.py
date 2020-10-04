from loguru import logger

from baldrick.plugins.github_comment_matcher import match_issue_comment


@match_issue_comment(".*", issue_type="pull")
def add_changelog_entry(pr_handler, repo_handler, comment, payload):
    logger.debug(f"Adding changelog entry to {pr_handler.repo}#{pr_handler.number}")
