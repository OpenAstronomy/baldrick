import sys
import time
import argparse
from humanize import naturaltime, naturaldelta

from baldrick.utils import unwrap
from baldrick.github.github_auth import repo_to_installation_id, get_app_name
from baldrick.github.github_api import IssueHandler, RepoHandler

ISSUE_CLOSE_WARNING = unwrap("""
Hi humans :wave: - this issue was labeled as **Close?** approximately
{pasttime}. If you think this issue should not be closed, a maintainer should
remove the **Close?** label - otherwise, I will close this issue in
{futuretime}.

*If you believe I commented on this issue incorrectly, please report this
[here](https://github.com/OpenAstronomy/baldrick/issues)*
""")


def is_close_warning(message):
    return 'Hi humans :wave: - this issue was labeled as **Close?**' in message


ISSUE_CLOSE_EPILOGUE = unwrap("""
I'm going to close this issue as per my previous message, but if you feel that
this issue should stay open, then feel free to re-open and remove the **Close?**
label.

*If this is the first time I am commenting on this issue, or if you believe I
closed this issue incorrectly, please report this
[here](https://github.com/OpenAstronomy/baldrick/issues)*
""")


def is_close_epilogue(message):
    return "I'm going to close this issue as per my previous message" in message


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

        time_since_close_label = now - labeled_time

        # Note: if warning time is before label time, it's as if the warning
        # didn't exist since it's no longer relevant.
        warning_time = issue.last_comment_date(f'{bot_name}[bot]', filter_keep=is_close_warning)
        if warning_time is None or warning_time < labeled_time:
            time_since_last_warning = -1.
        else:
            # We use max() here to make sure that the value is positive
            time_since_last_warning = max(0, now - warning_time)

        # We only close issues if there has been a warning before, and
        # the time since the warning exceeds the threshold specified by
        # close_seconds.

        if time_since_last_warning > close_seconds:
            comment_ids = issue.find_comments(f'{bot_name}[bot]', filter_keep=is_close_epilogue)
            if len(comment_ids) == 0:
                print(f'-> CLOSING issue {n}')
                issue.set_labels(['closed-by-bot'])
                issue.submit_comment(ISSUE_CLOSE_EPILOGUE)
                issue.close()
            else:
                print(f'-> Skipping issue {n} (already closed)')
        elif time_since_close_label > warn_seconds:
            comment_ids = issue.find_comments(f'{bot_name}[bot]', filter_keep=is_close_warning)
            if len(comment_ids) == 0:
                print(f'-> WARNING issue {n}')
                issue.submit_comment(ISSUE_CLOSE_WARNING.format(pasttime=naturaltime(time_since_close_label),
                                                                futuretime=naturaldelta(close_seconds)))
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
