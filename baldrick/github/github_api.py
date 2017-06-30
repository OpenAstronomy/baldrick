import requests

from changebot.github_auth import github_request_headers

__all__ = ['submit_review', 'set_status', 'fill_pull_request_from_issue']


def submit_review(pull_request_payload, decision, body):
    """
    Submit a review comment to a pull request on GitHub.

    Parameters
    ----------
    pull_request_payload : dict
        The payload sent from GitHub via the webhook interface
    decision : { 'approve' | 'request_changes' | 'comment' }
        The decision as to whether to aprove or reject the changes so far.
    body : str
        The body of the review comment
    """

    url_review = pull_request_payload['pull_request']['review_comments_url'].replace('comments', 'reviews')

    data = {}
    data['commit_id'] = pull_request_payload['pull_request']['head']['sha']
    data['body'] = body
    data['event'] = decision.upper()

    headers = github_request_headers(pull_request_payload['installation']['id'])

    requests.post(url_review, json=data, headers=headers)


def set_status(pull_request_payload, state, description, context):
    """
    Set status message in a pull request on GitHub.

    Parameters
    ----------
    pull_request_payload : dict
        The payload sent from GitHub via the webhook interface.
    state : { 'pending' | 'error' | 'pass' }
        The state to set for the pull request.
    description : str
        The message that appears in the status line.
    context : str
         A string used to identify the status line.
    """

    url_status = pull_request_payload['pull_request']['statuses_url']

    data = {}
    data['state'] = state
    data['description'] = description
    data['context'] = context

    headers = github_request_headers(pull_request_payload['installation']['id'])

    requests.post(url_status, json=data, headers=headers)


def fill_pull_request_from_issue(pull_request_payload):

    url_pull_request = pull_request_payload['issue']['pull_request']['url']

    headers = github_request_headers(pull_request_payload['installation']['id'])

    response = requests.get(url_pull_request, headers=headers)

    pull_request_payload['pull_request'] = response.json()
    pull_request_payload['number'] = pull_request_payload['pull_request']['number']
