import json
from pprint import pformat

from flask import Blueprint, request
from loguru import logger

from baldrick.github.github_api import RepoHandler
from baldrick.github.github_auth import repo_to_installation_id_mapping

__all__ = ["circleci_blueprint", "circleci_webhook_handler"]

circleci_blueprint = Blueprint("circleci", __name__)


CIRCLECI_WEBHOOK_HANDLERS = []


def circleci_webhook_handler(func):
    """
    Add a function that gets called when a circleci webhook is received.

    The functions decorated with this decorator will be called with
    ``(repo_handler, payload, headers)``. Nothing will be done with the return values.
    """
    CIRCLECI_WEBHOOK_HANDLERS.append(func)
    return func


def _run_circleci_handlers(repo_handler, version, payload, status, revision, build_num):
    for handler in CIRCLECI_WEBHOOK_HANDLERS:
        try:
            handler(repo_handler, version, payload, request.headers, status, revision, build_num)
        except Exception:  # noqa BLE001
            handler_name = getattr(handler, "__name__", str(handler))
            logger.exception(f"CircleCI webhook handler {handler_name} failed for {repo_handler.repo}")


def _get_installed_repos():
    try:
        return repo_to_installation_id_mapping()
    except Exception:  # noqa BLE001
        logger.exception("Failed to fetch the list of installations of this bot from GitHub")
        return None


@circleci_blueprint.route("/circleci", methods=["POST"])
def circleci_handler():

    if not request.data:
        logger.warning("Rejecting CircleCI webhook without a payload.")
        return "No payload received", 400

    try:
        payload = json.loads(request.data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Rejecting CircleCI webhook with a payload that is not valid JSON.")
        return "Payload is not valid JSON", 400

    payload = payload.get("payload") if isinstance(payload, dict) else None

    if not isinstance(payload, dict):
        logger.warning("Rejecting CircleCI webhook without a payload object.")
        return "Payload missing payload object", 400

    # Validate we have the keys we need, otherwise ignore the push
    required_keys = {"vcs_revision", "username", "reponame", "status", "build_num"}

    if not required_keys.issubset(payload.keys()):
        missing = " ".join(sorted(required_keys - payload.keys()))
        logger.warning(f"Rejecting CircleCI webhook with a payload missing {missing}.")
        return f"Payload missing {missing}", 400

    # Get installation id
    repos = _get_installed_repos()
    if repos is None:
        return "Failed to fetch installations from GitHub", 502

    repo = f"{payload['username']}/{payload['reponame']}"

    if repo not in repos:
        logger.debug(f"circleci: Not installed for {repo}, ignoring.")
        return f"circleci: Not installed for {repo}"

    repo_handler = RepoHandler(repo, branch="main", installation=repos[repo])

    _run_circleci_handlers(
        repo_handler, "v1", payload, payload["status"], payload["vcs_revision"], payload["build_num"]
    )

    return "CircleCI Webhook Finished"


@circleci_blueprint.route("/circleci/v2", methods=["POST"])
def circleci_new_handler():
    if not request.data:
        return "No payload received", 400

    try:
        payload = json.loads(request.data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Rejecting CircleCI v2 webhook with a payload that is not valid JSON.")
        return "Payload is not valid JSON", 400

    logger.debug(f"Got {pformat(payload)} on /circleci/v2")

    if not isinstance(payload, dict):
        return "Payload is not a JSON object", 400

    # Validate we have the keys we need, otherwise ignore the push
    required_keys = {
        "job",
        "pipeline",
    }

    if not required_keys.issubset(payload.keys()):
        msg = "Payload missing {}".format(" ".join(required_keys - payload.keys()))
        logger.error(msg)
        return msg, 400

    vcs = payload["pipeline"]["vcs"]

    if vcs["provider_name"] != "github":
        msg = "Only GitHub repositories are supported."
        logger.error(msg)
        return msg

    # Get installation id
    try:
        repos = repo_to_installation_id_mapping()
    except Exception:  # noqa BLE001
        logger.exception("Failed to fetch the list of installations of this bot from GitHub")
        return "Failed to fetch installations from GitHub", 502

    if repo not in repos:
        msg = f"Not installed for {repo}"
        logger.error(msg)
        logger.trace(f"Only installed for {repos.keys()}")
        return msg

    repo_handler = RepoHandler(repo, branch=vcs["branch"], installation=repos[repo])

    for handler in CIRCLECI_WEBHOOK_HANDLERS:
        try:
            handler(
                repo_handler,
                "v2",
                payload,
                request.headers,
                payload["job"].get("status"),
                vcs["revision"],
                payload["job"]["number"],
            )
        except Exception:  # noqa BLE001
            handler_name = getattr(handler, "__name__", str(handler))
            logger.exception(f"CircleCI webhook handler {handler_name} failed for {repo_handler.repo}")

    return "CirleCI Webhook Finished"
