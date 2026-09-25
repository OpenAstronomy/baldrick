import json
from pprint import pformat

from flask import Blueprint, request, current_app
from loguru import logger

from baldrick.github.github_api import RepoHandler

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
        repos = current_app.github_auth.repo_to_installation_id_mapping
    except Exception:  # noqa BLE001
        logger.exception("Failed to fetch the list of installations of this bot from GitHub")
        return "Failed to fetch installations from GitHub", 502

    repo = vcs["target_repository_url"].removeprefix("https://github.com/")

    if repo not in repos:
        msg = f"Not installed for {repo}"
        logger.error(msg)
        logger.trace(f"Only installed for {repos.keys()}")
        return msg

    repo_handler = RepoHandler(repo, installation=repos[repo])

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
