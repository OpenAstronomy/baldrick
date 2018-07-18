import re
import time
import json
from humanize import naturaldelta
from changebot.github.github_api import PullRequestHandler, RepoHandler
from flask import Blueprint, request, current_app, Response, stream_with_context

stale_pull_requests = Blueprint('stale_pull_requests', __name__)


@stale_pull_requests.route('/close_stale_pull_requests', methods=['POST'])
def close_stale_pull_requests():
    payload = json.loads(request.data)
    for keyword in ['repository', 'cron_token', 'installation']:
        if keyword not in payload:
            return f'Payload mising {keyword}'
    if payload['cron_token'] != current_app.cron_token:
        return "Incorrect cron_token"
    # process_pull_requests is a generator so that we can continuously return a
    # response to the requester - this prevents Heroku from thinking the
    # request has timed out (https://librenepal.com/article/flask-and-heroku-timeout/)
    return Response(stream_with_context(process_pull_requests(payload['repository'], payload['installation'])),
                    mimetype='text/plain')


PULL_REQUESTS_CLOSE_WARNING = re.sub('(\w+)\n', r'\1', """
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
""").strip()


# NOTE: This must be in-sync with PULL_REQUESTS_CLOSE_WARNING
def is_close_warning(message):
    return 'Hi humans :wave: - this pull request hasn\'t had any new commits' in message


PULL_REQUESTS_CLOSE_EPILOGUE = re.sub('(\w+)\n', r'\1', """
:alarm_clock: Time's up! :alarm_clock:

I'm going to close this pull request as per my previous message. If you
 think what is being added/fixed here is still important, please remember to
 open an issue to keep track of it. Thanks!

*If this is the first time I am commenting on this issue, or if you believe
 I closed this issue incorrectly, please report this
 [here](https://github.com/astropy/astropy-bot/issues).*
""").strip()


def is_close_epilogue(message):
    return "I'm going to close this pull request" in message


def process_pull_requests(repository, installation):

    now = time.time()

    # Get issues labeled as 'Close?'
    repo = RepoHandler(repository, 'master', installation)
    pull_requests = repo.open_pull_requests()

    # User config
    enable_autoclose = repo.get_config_value(
        'autoclose_stale_pull_request', True)

    for n in pull_requests:

        print(f'Checking {n}')
        yield f'Checking {n}'

        pr = PullRequestHandler(repository, n, installation)
        if 'keep-open' in pr.labels:
            print('-> PROTECTED by label, skipping')
            yield '-> PROTECTED by label, skipping'
            continue
        commit_time = pr.last_commit_date

        dt = now - commit_time

        if current_app.stale_pull_requests_close and dt > current_app.stale_pull_requests_close_seconds:
            comment_ids = pr.find_comments('astropy-bot[bot]', filter_keep=is_close_epilogue)
            if not enable_autoclose:
                print(f'-> Skipping issue {n} (auto-close disabled)')
                yield f'-> Skipping issue {n} (auto-close disabled)'
            elif len(comment_ids) == 0:
                print(f'-> CLOSING issue {n}')
                yield f'-> CLOSING issue {n}'
                pr.set_labels(['closed-by-bot'])
                pr.submit_comment(PULL_REQUESTS_CLOSE_EPILOGUE)
                pr.close()
            else:
                print(f'-> Skipping issue {n} (already closed)')
                yield f'-> Skipping issue {n} (already closed)'
        elif dt > current_app.stale_pull_requests_warn_seconds:
            comment_ids = pr.find_comments('astropy-bot[bot]', filter_keep=is_close_warning)
            if len(comment_ids) == 0:
                print(f'-> WARNING issue {n}')
                yield f'-> WARNING issue {n}'
                pr.submit_comment(PULL_REQUESTS_CLOSE_WARNING.format(pasttime=naturaldelta(dt),
                                                                     futuretime=naturaldelta(current_app.stale_pull_requests_close_seconds - current_app.stale_pull_requests_warn_seconds)))
            else:
                print(f'-> Skipping issue {n} (already warned)')
                yield f'-> Skipping issue {n} (already warned)'
        else:
            print(f'-> OK issue {n}')
            yield f'-> OK issue {n}'

    print('Finished checking for stale pull requests')
    yield 'Finished checking for stale pull requests'
