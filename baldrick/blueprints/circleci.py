import json

from loguru import logger

from baldrick.github.github_auth import repo_to_installation_id_mapping
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
    repos = repo_to_installation_id_mapping()
    repo = f"{payload['username']}/{payload['reponame']}"

    if repo not in repos:
        return f"circleci: Not installed for {repo}"

    repo_handler = RepoHandler(repo, branch="master", installation=repos[repo])

    for handler in CIRCLECI_WEBHOOK_HANDLERS:
        handler(repo_handler, payload, request.headers, payload["status"], payload["vcs_revision"], payload["build_num"])

    return "CirleCI Webhook Finished"


@circleci_blueprint.route('/circleci/v2', methods=['POST'])
def circleci_new_handler():
    if not request.data:
        return "No payload received"

    payload = json.loads(request.data)

    # Validate we have the keys we need, otherwise ignore the push
    required_keys = {'workflow',
                     'pipeline'}

    if not required_keys.issubset(payload.keys()):
        msg = 'Payload missing {}'.format(' '.join(required_keys - payload.keys()))
        logger.error(msg)
        return msg

    vcs = payload["pipeline"]["vcs"]

    if vcs["provider_name"] != "github":
        msg = "Only GitHub repositories are supported."
        logger.error(msg)
        return msg

    # Get installation id
    repos = repo_to_installation_id_mapping()

    repo = vcs["origin_repository_url"].removeprefix("https://github.com/")

    if repo not in repos:
        msg = f"Not installed for {repo}"
        logger.error(msg)
        logger.trace(f"Only installed for {repos}")
        return msg

    repo_handler = RepoHandler(repo, branch=vcs["branch"], installation=repos[repo])

    for handler in CIRCLECI_WEBHOOK_HANDLERS:
        handler(repo_handler,
                payload,
                request.headers,
                payload["workflow"]["status"],
                vcs["revision"],
                payload["pipeline"]["number"])

    return "CirleCI Webhook Finished"
