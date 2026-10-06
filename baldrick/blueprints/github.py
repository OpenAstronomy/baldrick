import json

from flask import Blueprint, request
from loguru import logger

from baldrick.github import github_auth
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


def handle_installation_event(event, payload):
    """
    Update the cached installation mapping in response to an
    ``installation`` or ``installation_repositories`` webhook event.

    These events have no ``repository`` field, so they are dispatched before
    the repository/installation extraction in :func:`github_webhook`.
    """
    action = payload.get("action")
    installation_id = (payload.get("installation") or {}).get("id")
    if installation_id is None:
        return

    if event == "installation":
        if action in ("created", "unsuspended"):
            github_auth.add_installation(installation_id)
        elif action in ("deleted", "suspended"):
            github_auth.remove_installation(installation_id)
        # Other actions (e.g. new_permissions_accepted) are no-ops.

    elif event == "installation_repositories":
        if action == "added":
            repos = [r["full_name"] for r in payload.get("repositories_added", [])]
            github_auth.add_repositories_to_installation(installation_id, repos)
        elif action == "removed":
            repos = [r["full_name"] for r in payload.get("repositories_removed", [])]
            github_auth.remove_repositories_from_installation(repos)


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

    event = request.headers.get("X-GitHub-Event")
    if event in ("installation", "installation_repositories"):
        try:
            handle_installation_event(event, payload)
        except Exception:  # noqa: BLE001
            logger.exception(f"Failed to process {event} webhook delivery {delivery}")
            return "Failed to update installation cache", 502
        logger.debug("Updated installation cache")
        return "Installation cache updated"

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
