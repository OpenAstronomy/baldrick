import sys
import time
import argparse
from humanize import naturaldelta

from baldrick.utils import unwrap
from baldrick.github.github_auth import repo_to_installation_id, get_app_name
from baldrick.github.github_api import PullRequestHandler, RepoHandler

PULL_REQUESTS_CLOSE_WARNING = unwrap("""
Hi humans :wave: - this pull request hasn't had any new commits for
 approximately {pasttime}. **I plan to close this in {futuretime} if the pull
 request doesn't have any new commits by then.**

In lieu of a stalled pull request, please consider closing this and open an
 issue instead if a reminder is needed to revisit in the future. Maintainers
 may also choose to add `keep-open` label to keep this PR open but it is
 discouraged unless absolutely necessary.

If this PR still needs to be reviewed, as an author, you can rebase it
 to reset the clock. You may also consider sending a reminder e-mail about it
 to the [astropy-dev mailing list](http://groups.google.com/group/astropy-dev).

*If you believe I commented on this pull request incorrectly, please report
 this [here](https://github.com/astropy/astropy-bot/issues).*
""")


# NOTE: This must be in-sync with PULL_REQUESTS_CLOSE_WARNING
def is_close_warning(message):
    return 'Hi humans :wave: - this pull request hasn\'t had any new commits' in message


PULL_REQUESTS_CLOSE_EPILOGUE = unwrap("""
:alarm_clock: Time's up! :alarm_clock:

I'm going to close this pull request as per my previous message. If you
 think what is being added/fixed here is still important, please remember to
 open an issue to keep track of it. Thanks!

*If this is the first time I am commenting on this issue, or if you believe
 I closed this issue incorrectly, please report this
 [here](https://github.com/astropy/astropy-bot/issues).*
""")


def is_close_epilogue(message):
    return "I'm going to close this pull request" in message


def process_pull_requests(repository, installation,
                          warn_seconds=None,
                          close_seconds=None):

    now = time.time()

    # Find app name
    bot_name = get_app_name()

    # Get issues labeled as 'Close?'
    repo = RepoHandler(repository, 'master', installation)
    pull_requests = repo.open_pull_requests()

    # User config
    enable_autoclose = repo.get_config_value('autoclose_stale_pull_request', True)

    for n in pull_requests:

        print(f'Checking {n}')

        pr = PullRequestHandler(repository, n, installation)
        if 'keep-open' in pr.labels:
            print('-> PROTECTED by label, skipping')
            continue

        commit_time = pr.last_commit_date
        time_since_last_commit = now - commit_time

        # Note: if warning time is before commit time, it's as if the warning
        # didn't exist since it's no longer relevant.
        warning_time = pr.last_comment_date(f'{bot_name}[bot]', filter_keep=is_close_warning)
        if warning_time is None or warning_time < commit_time:
            time_since_last_warning = -1.
        else:
            # We use max() here to make sure that the value is positive
            time_since_last_warning = max(0, now - warning_time)

        # We only close pull requests if there has been a warning before, and
        # the time since the warning exceeds the threshold specified by
        # stale_pull_requests_close_seconds.

        if time_since_last_warning > close_seconds:
            comment_ids = pr.find_comments(f'{bot_name}[bot]', filter_keep=is_close_epilogue)
            if not enable_autoclose:
                print(f'-> Skipping pull request {n} (auto-close disabled)')
            elif len(comment_ids) == 0:
                print(f'-> CLOSING pull request {n}')
                pr.set_labels(['closed-by-bot'])
                pr.submit_comment(PULL_REQUESTS_CLOSE_EPILOGUE)
                pr.close()
            else:
                print(f'-> Skipping pull request {n} (already closed)')
        elif time_since_last_commit > warn_seconds:
            # A negative time_since_last_warning means no warning since last commit.
            if time_since_last_warning < 0.:
                print(f'-> WARNING pull request {n}')
                pr.submit_comment(PULL_REQUESTS_CLOSE_WARNING.format(pasttime=naturaldelta(time_since_last_commit),
                                                                     futuretime=naturaldelta(close_seconds)))
            else:
                print(f'-> Skipping pull request {n} (already warned)')
        else:
            print(f'-> OK pull request {n}')

    print('Finished checking for stale pull requests')


def main(argv=None):

    parser = argparse.ArgumentParser(description='Check for stale pull requests and close them if needed.')

    parser.add_argument('--repository', dest='repository', required=True,
                        help='The repository in which to check for stale pull requests')

    parser.add_argument('--warn-seconds', dest='warn_seconds', action='store',
                        type=int, required=True,
                        help='After how many seconds to warn about stale issues')

    parser.add_argument('--close-seconds', dest='close_seconds', action='store',
                        type=int, required=True,
                        help='After how many seconds to close stale issues')

    args = parser.parse_args(argv or sys.argv[1:])

    installation = repo_to_installation_id(args.repository)

    process_pull_requests(args.repository, installation,
                          warn_seconds=args.warn_seconds, close_seconds=args.close_seconds)
