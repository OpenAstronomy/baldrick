from datetime import UTC, datetime, timedelta

from loguru import logger

from baldrick.plugins.github_pull_requests import pull_request_handler

CLOSE_MESSAGE = """\
Hi 👋 and thank you for your contribution! 🙏

This pull request is being closed automatically - but don't worry, this is not the end, and we may re-open it.

For some background, we have recently started seeing a rapid increase in the number of pull requests opened. Some of these are from good-faith humans, but some of which are from autonomous LLM agents or humans using LLMs who do not have a genuine understanding of, or interest in, the project. We are therefore auto-closing pull requests from new contributors, but if you are a good-faith human, we want to make sure your pull request gets considered! So if you would like us to re-open your pull request so that it gets reviewed, you need to do two things:

1. Add a comment here to explain why you need the changes here to be considered, as in how the bug or missing feature affects your work, or whether this is an issue you have encountered but does not affect you.

2. Join the astropy slack using [this invite link](https://join.slack.com/t/astropy/shared_invite/zt-4c1p8lbom-GuaB46o3rPd0ZRJh6MR_kQ) and head over to the **#hello** channel to introduce yourself and let us know about this pull request

The second step is important, as we may otherwise miss notifications about this pull request.

To be clear, our [AI policy](https://github.com/astropy/astropy-project/blob/main/policies/ai-policy.md) does allow the use of LLMs as part of contributions, _but_ we need to see authentic engagement and understanding from humans making the contribution.

### Notes for maintainers

{previous_prs}

In addition, here are some statistics on the user's activity on GitHub:

|                      | Last 24 hours | Last 7 days |
| -------------------- | ------------: | ----------: |
| Pull requests opened | {pr_day} | {pr_week} |
| Issues opened        | {issue_day} | {issue_week} |
"""


def previous_pull_requests_notes(pr_handler, repo_handler):
    """
    Describe the other pull requests the author has opened on this repository.
    """
    previous_prs = [n for n in repo_handler.get_pull_requests_by(pr_handler.user) if n != int(pr_handler.number)]
    if not previous_prs:
        return "This user has not made any other pull requests to this repository prior to this one."
    pr_list = "\n".join(f"* #{n}" for n in previous_prs)
    return f"This user has made other pull requests to this repository prior to this one, here is a full list:\n\n{pr_list}"


def activity_counts(pr_handler, repo_handler):
    """
    Count the issues and pull requests the author has opened GitHub-wide over
    the last day and the last week.
    """
    now = datetime.now(UTC)
    counts = {}
    for period, delta in (("day", timedelta(days=1)), ("week", timedelta(days=7))):
        for kind in ("pr", "issue"):
            counts[f"{kind}_{period}"] = repo_handler.count_opened_by(pr_handler.user, kind, now - delta)
    return counts


@pull_request_handler(actions=["opened"])
def close_if_not_in_org(pr_handler, repo_handler):

    # When a PR is first opened, we check if the contributor is in the
    # organization, and if not, we close the pull request and post a friendly
    # message encouraging contributors to re-open

    vet_config = pr_handler.get_config_value("org_vetting", {})
    if not vet_config.get("enabled", False):
        logger.debug("Skipping org vetting plugin as disabled in config")
        return None

    logger.debug(f"Checking if {pr_handler.user} is a member of org")

    if repo_handler.org_handler.is_member(pr_handler.user):
        logger.debug(f"Yes they are")
        return

    logger.debug(f"No they are not, posting comment")

    message = CLOSE_MESSAGE.format(
        previous_prs=previous_pull_requests_notes(pr_handler, repo_handler),
        **activity_counts(pr_handler, repo_handler),
    )

    pr_handler.submit_comment(message)
    pr_handler.close()


@pull_request_handler(actions=["reopened"])
def vetting_keep_closed(pr_handler, repo_handler):

    vet_config = pr_handler.get_config_value("org_vetting", {})
    if not vet_config.get("enabled", False):
        logger.debug("Skipping org vetting plugin as disabled in config")
        return

    if repo_handler.org_handler.is_member(pr_handler.user):
        logger.debug(f"PR author is an organization member, so no vetting is required")
        return

    user = pr_handler.last_opened_by

    logger.debug(f"Checking last person who opened PR ({user}) is a maintainer")

    if repo_handler.is_maintainer(user):
        logger.debug(f"{user} is a maintainer, so re-opening is allowed")
        return

    logger.debug(f"{user} is not a maintainer, disallowing re-opening")

    pr_handler.submit_comment("Only a maintainer can re-open this pull request")
    pr_handler.close()
