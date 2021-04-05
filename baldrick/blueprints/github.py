import json

from flask import Blueprint, request

from baldrick.github.github_api import RepoHandler

__all__ = ['github_blueprint', 'github_webhook_handler']


github_blueprint = Blueprint('github', __name__)


GITHUB_WEBHOOK_HANDLERS = []


def github_webhook_handler(func):
    """
    A decorator to add functions to the GitHub webhook handler.


    The functions decorated with this decorator will be passed
    ``(repo_handler, payload, headers)``
    """
    GITHUB_WEBHOOK_HANDLERS.append(func)
    return func


@github_blueprint.route('/github', methods=['POST'])
def github_webhook():

    if not request.data:
        return "No payload received"

    # Parse the JSON sent by GitHub
    payload = json.loads(request.data)

    if 'installation' not in payload:
        return "No installation key found in payload"
    else:
        installation = payload['installation']['id']

    repo_name = payload['repository']['full_name']
    repo = RepoHandler(repo_name, branch='main', installation=installation)

    for handler in GITHUB_WEBHOOK_HANDLERS:
        handler(repo, payload, request.headers)

    return "GitHub Webhook Finished"
