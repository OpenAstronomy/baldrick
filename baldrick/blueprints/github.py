import json

from flask import Blueprint, request
from loguru import logger

from baldrick.github.github_api import RepoHandler
from baldrick.webhooks import verify_github_webhook

__all__ = ["github_blueprint", "github_webhook_handler"]


github_blueprint = Blueprint("github", __name__)


GITHUB_WEBHOOK_HANDLERS = []


def github_webhook_handler(func):
    """
    A decorator to add functions to the GitHub webhook handler.


    The functions decorated with this decorator will be passed
    ``(repo_handler, payload, headers)``
    """
    GITHUB_WEBHOOK_HANDLERS.append(func)
    return func


@github_blueprint.route("/github", methods=["POST"])
def github_webhook():

    delivery = request.headers.get("X-GitHub-Delivery", "unknown")

    if not verify_github_webhook(request.data, request.headers.get("X-Hub-Signature-256")):
        logger.warning(f"Rejecting GitHub webhook delivery {delivery} with a missing or invalid signature.")
        return "Invalid or missing webhook signature", 403

    if not request.data:
        logger.warning(f"Rejecting GitHub webhook delivery {delivery} without a payload.")
        return "No payload received", 400

    try:
        payload = json.loads(request.data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning(f"Rejecting GitHub webhook delivery {delivery} with a payload that is not valid JSON.")
        return "Payload is not valid JSON", 400

    if not isinstance(payload, dict):
        logger.warning(f"Rejecting GitHub webhook delivery {delivery} with a payload that is not a JSON object.")
        return "Payload is not a JSON object", 400

    installation_id = (payload.get("installation") or {}).get("id")
    repo_name = (payload.get("repository") or {}).get("full_name")

    if installation_id is None or repo_name is None:
        if request.headers.get("X-GitHub-Event") == "ping" or "hook_id" in payload:
            logger.debug(f"Received ping event for delivery {delivery}, nothing to do.")
            return "Ping received"
        logger.warning(f"Rejecting GitHub webhook delivery {delivery} without installation or repository information.")
        return "Payload missing installation or repository", 400

    repo = RepoHandler(repo_name, installation=installation_id)

    for handler in GITHUB_WEBHOOK_HANDLERS:
        try:
            handler(repo, payload, request.headers)
        except Exception:  # noqa BLE001
            handler_name = getattr(handler, "__name__", str(handler))
            logger.exception(f"GitHub webhook handler {handler_name} failed for delivery {delivery}")

    return "GitHub Webhook Finished"
