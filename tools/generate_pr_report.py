import argparse
from os import environ
from unittest.mock import patch

from baldrick.github.github_api import RepoHandler, PullRequestHandler
from baldrick.plugins.github_org_vetting import previous_pull_requests_notes, activity_counts, MAINTAINER_NOTES


def get_installation_token(installation):
    return environ["GITHUB_TOKEN"]


@patch("baldrick.github.github_auth.get_installation_token", get_installation_token)
def report_pr_stats(repo_name, pr_number):
    """
    Use Baldrick to report PR stats.
    """
    repo_handler = RepoHandler(repo_name)
    pr_handler = PullRequestHandler(repo_name, pr_number)

    print(
        MAINTAINER_NOTES.format(
            preamble="",
            previous_prs=previous_pull_requests_notes(pr_handler, repo_handler),
            **activity_counts(pr_handler, repo_handler),
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="generate_pr_report.py",
        description="Generate a report for a pull request, requires the GITHUB_TOKEN environment variable.",
    )
    parser.add_argument("repo_name", help="Repository name, e.g. owner/repo")
    parser.add_argument("pr_number", type=int, help="Pull request number")

    args = parser.parse_args()

    report_pr_stats(args.repo_name, int(args.pr_number))
