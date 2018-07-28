import sys
import time
import argparse
from humanize import naturaltime, naturaldelta

from baldrick.utils import unwrap
from baldrick.github.github_auth import repo_to_installation_id, get_app_name
from baldrick.github.github_api import IssueHandler, RepoHandler

ISSUE_CLOSE_WARNING = unwrap("""
Hi humans :wave: - this issue was labeled as **Close?** approximately
{pasttime}. So..... any news? :newspaper_roll:

If you think this issue should not be closed, a maintainer should remove the
**Close?** label - otherwise, I'm just gonna have to close this issue in
{futuretime}. Your time starts now! Tick tock :clock10:

*If you believe I commented on this issue incorrectly, please report this
*[here](https://github.com/astrofrog/baldrick/issues)*
""")


def is_close_warning(message):
    return 'Hi humans :wave: - this issue was labeled as **Close?**' in message


ISSUE_CLOSE_EPILOGUE = unwrap("""
:alarm_clock: Time's up! :alarm_clock:

I'm going to close this issue as per my previous message. But if you feel that
we should really really keep this open, then feel free to re-open and remove the
**Close?** label. But no one has done anything for 6 months, so... Just sayin'!

*If this is the first time I am commenting on this issue, or if you believe I
*closed this issue incorrectly, please report this
*[here](https://github.com/astrofrog/baldrick/issues)*
""")


def is_close_epilogue(message):
    return ":alarm_clock: Time's up! :alarm_clock:" in message


def process_issues(repository, installation,
                   warn_seconds=None,
                   close_seconds=None):

    now = time.time()

    # Find app name
    bot_name = get_app_name()

    # Get issues labeled as 'Close?'
    repo = RepoHandler(repository, 'master', installation)
    issuelist = repo.get_issues('open', 'Close?')

    for n in issuelist:

        print(f'Checking {n}')

        issue = IssueHandler(repository, n, installation)
        labeled_time = issue.get_label_added_date('Close?')
        if labeled_time is None:
            continue

        dt = now - labeled_time

        if dt > close_seconds:
            comment_ids = issue.find_comments(f'{bot_name}[bot]', filter_keep=is_close_epilogue)
            if len(comment_ids) == 0:
                print(f'-> CLOSING issue {n}')
                issue.set_labels(['closed-by-bot'])
                issue.submit_comment(ISSUE_CLOSE_EPILOGUE)
                issue.close()
            else:
                print(f'-> Skipping issue {n} (already closed)')
        elif dt > warn_seconds:
            comment_ids = issue.find_comments(f'{bot_name}[bot]', filter_keep=is_close_warning)
            if len(comment_ids) == 0:
                print(f'-> WARNING issue {n}')
                issue.submit_comment(ISSUE_CLOSE_WARNING.format(pasttime=naturaltime(dt),
                                                                futuretime=naturaldelta(close_seconds - warn_seconds)))
            else:
                print(f'-> Skipping issue {n} (already warned)')
        else:
            print(f'-> OK issue {n}')

    print('Finished checking for stale issues')


def main(argv=None):

    parser = argparse.ArgumentParser(description='Check for stale issues and close them if needed.')

    parser.add_argument('--repository', dest='repository', required=True,
                        help='The repository in which to check for stale issues')

    parser.add_argument('--warn-seconds', dest='warn_seconds', action='store',
                        type=int, required=True,
                        help='After how many seconds to warn about stale issues')

    parser.add_argument('--close-seconds', dest='close_seconds', action='store',
                        type=int, required=True,
                        help='After how many seconds to close stale issues')

    args = parser.parse_args(argv or sys.argv[1:])

    installation = repo_to_installation_id(args.repository)

    process_issues(args.repository, installation,
                   warn_seconds=args.warn_seconds, close_seconds=args.close_seconds)
