import json
import time
from humanize import naturaltime, naturaldelta
from changebot.github.github_api import IssueHandler, RepoHandler
from flask import Blueprint, request, current_app, Response, stream_with_context

stale_issues = Blueprint('stale_issues', __name__)


@stale_issues.route('/close_stale_issues', methods=['POST'])
def close_stale_issues():
    payload = json.loads(request.data)
    for keyword in ['repository', 'cron_token', 'installation']:
        if keyword not in payload:
            return f'Payload mising {keyword}'
    if payload['cron_token'] != current_app.cron_token:
        return "Incorrect cron_token"
    # process_issues is a generator so that we can continuously return a
    # response to the requester - this prevents Heroku from thinking the
    # request has timed out (https://librenepal.com/article/flask-and-heroku-timeout/)
    return Response(stream_with_context(process_issues(payload['repository'], payload['installation'])),
                    mimetype='text/plain')


ISSUE_CLOSE_WARNING = """
Hi humans :wave: - this issue was labeled as **Close?** approximately {pasttime}. So..... any news? :newspaper_roll:

If you think this issue should not be closed, a maintainer should remove the **Close?** label - otherwise, I'm just gonna have to close this issue in {futuretime}. Your time starts now! Tick tock :clock10:

*If you believe I commented on this issue incorrectly, please report this [here](https://github.com/astropy/astropy-bot/issues)*
"""


def is_close_warning(message):
    return 'Hi humans :wave: - this issue was labeled as **Close?**' in message


ISSUE_CLOSE_EPILOGUE = """
:alarm_clock: Time's up! :alarm_clock:

I'm going to close this issue as per my previous message. But if you feel that we should really really keep this open, then feel free to re-open and remove the **Close?** label. But no one has done anything for 6 months, so... Just sayin'!

*If this is the first time I am commenting on this issue, or if you believe I closed this issue incorrectly, please report this [here](https://github.com/astropy/astropy-bot/issues)*
"""


def is_close_epilogue(message):
    return ":alarm_clock: Time's up! :alarm_clock:" in message


def process_issues(repository, installation):

    now = time.time()

    # Get issues labeled as 'Close?'
    repo = RepoHandler(repository, 'master', installation)
    issuelist = repo.get_issues('open', 'Close?')

    for n in issuelist:

        print(f'Checking {n}')
        yield f'Checking {n}\n'

        issue = IssueHandler(repository, n, installation)
        labeled_time = issue.get_label_added_date('Close?')
        if labeled_time is None:
            continue

        dt = now - labeled_time

        if current_app.stale_issue_close and dt > current_app.stale_issue_close_seconds:
            comment_ids = issue.find_comments('astropy-bot[bot]', filter_keep=is_close_epilogue)
            if len(comment_ids) == 0:
                print(f'-> CLOSING issue {n}')
                yield f'-> CLOSING issue {n}\n'
                issue.set_labels(['closed-by-bot'])
                issue.submit_comment(ISSUE_CLOSE_EPILOGUE)
                issue.close()
            else:
                print(f'-> Skipping issue {n} (already closed)')
                yield f'-> Skipping issue {n} (already closed)\n'
        elif dt > current_app.stale_issue_warn_seconds:
            comment_ids = issue.find_comments('astropy-bot[bot]', filter_keep=is_close_warning)
            if len(comment_ids) == 0:
                print(f'-> WARNING issue {n}')
                yield f'-> WARNING issue {n}\n'
                issue.submit_comment(ISSUE_CLOSE_WARNING.format(pasttime=naturaltime(dt),
                                                                futuretime=naturaldelta(current_app.stale_issue_close_seconds - current_app.stale_issue_warn_seconds)))
            else:
                print(f'-> Skipping issue {n} (already warned)')
                yield f'-> Skipping issue {n} (already warned)\n'
        else:
            print(f'-> OK issue {n}')
            yield f'-> OK issue {n}\n'

    print('Finished checking for stale issues')
    yield 'Finished checking for stale issues\n'
