import time
from changebot.github_api import PullRequestHandler, RepoHandler


PRS_CLOSE_WARNING = """
Hi humans :wave: - this PR hasn't had any new commits for approximately 5 months. Of course, in this day and age we all have way too much on our plates (especially me!) but in the interest on making sure that we don't keep pull requests open if they are no longer relevant, **I plan to close this in a month if the pull request doesn't have any new commits by then.**

If you **really** want to keep this PR open beyond because it needs more discussion, then you can get a maintainer to add the **keep-open** label, but please only use this in rare cases. A better solution if you don't agree to merge this now is to close this and open a new issue to remind ourselves this should be done (for example if this PR is the wrong approach).

In any case, I will close this within a month unless there is a new commit or the **keep-open** label has been added. Thanks!

*If you believe I commented on this issue incorrectly, please report this [here](https://github.com/astropy/astropy-bot/issues)*
"""


def is_close_warning(message):
    return 'Hi humans :wave: - this PR hasn\'t had any new commits' in message


PRS_CLOSE_EPILOGUE = """
:alarm_clock: Time's up! :alarm_clock:

I'm going to close this pull request as per my previous message. If you think what is being added/fixed here is still important, please remember to open an issue to keep track of it. Thanks!

*If this is the first time I am commenting on this issue, or if you believe I closed this issue incorrectly, please report this [here](https://github.com/astropy/astropy-bot/issues)*
"""


def is_close_epilogue(message):
    return "I'm going to close this pull request" in message


def process_prs(repository, installation):

    from .webapp import app

    now = time.time()

    # Get issues labeled as 'Close?'
    repo = RepoHandler(repository, 'master', installation)
    pull_requests = repo.open_pull_requests()

    for n in pull_requests:

        print(f'Checking {n}')

        pr = PullRequestHandler(repository, n, installation)
        if 'keep-open' in pr.labels:
            print('-> PROTECTED by label, skipping')
            continue
        commit_time = pr.last_commit_date

        dt = now - commit_time

        if app.stale_prs_close and dt > app.stale_prs_close_seconds:
            comment_ids = pr.find_comments('astropy-bot[bot]', filter_keep=is_close_epilogue)
            if len(comment_ids) == 0:
                print(f'-> CLOSING issue {n}')
                pr.submit_comment(PRS_CLOSE_EPILOGUE)
                pr.close()
            else:
                print(f'-> Skipping issue {n} (already closed)')
        elif dt > app.stale_prs_warn_seconds:
            comment_ids = pr.find_comments('astropy-bot[bot]', filter_keep=is_close_warning)
            if len(comment_ids) == 0:
                print(f'-> WARNING issue {n}')
                pr.submit_comment(PRS_CLOSE_WARNING)
            else:
                print(f'-> Skipping issue {n} (already warned)')
        else:
            print(f'-> OK issue {n}')
