import json

from baldrick.github.github_auth import repo_to_installationid_mapping
from baldrick.github.github_api import RepoHandler

from flask import Blueprint, request

__all__ = ['circleci_blueprint', 'circleci_webhook_handler']

circleci_blueprint = Blueprint('circleci', __name__)


CIRCLECI_WEBHOOK_HANDLERS = []


def circleci_webhook_handler(func):
    """
    Add a function that gets called when a circleci webhook is received.

    The functions decorated with this decorator will be called with
    ``(repo_handler, payload, headers)``. Nothing will be done with the return values.
    """
    CIRCLECI_WEBHOOK_HANDLERS.append(func)
    return func


@circleci_blueprint.route('/circleci', methods=['POST'])
def circleci_handler():

    if not request.data:
        return "No payload received"

    payload = json.loads(request.data)['payload']

    # Validate we have the keys we need, otherwise ignore the push
    required_keys = {'vcs_revision',
                     'username',
                     'reponame',
                     'status',
                     'build_num'}

    if not required_keys.issubset(payload.keys()):
        return 'Payload missing {}'.format(' '.join(required_keys - payload.keys()))

    # Get installation id
    repos = repo_to_installationid_mapping()
    repo = f"{payload['username']}/{payload['reponame']}"

    if repo not in repos:
        return f"circleci: Not installed for {repo}"

    repo_handler = RepoHandler(repo, branch="master", installation=repos[repo])

    for handler in CIRCLECI_WEBHOOK_HANDLERS:
        handler(repo_handler, payload, request.headers)

    return "CirleCI Webhook Finsihed"
