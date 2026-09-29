from baldrick.plugins.github_pull_requests import pull_request_handler


@pull_request_handler(actions=["opened"])
def close_if_not_in_org(pr_handler, repo_handler):

    # When a PR is first opened, we check if the contributor is in the
    # organization, and if not, we close the pull request and post a friendly
    # message encouraging contributors to re-open

    if repo_handler.org_handler.is_member(pr_handler.user):
        return

    pr_handler.submit_comment("Your PR has been closed. But fear not, there is a way out!")
    pr_handler.close()
