from baldrick.github.github_api import RepoHandler
from baldrick.blueprints.github import github_webhook_handler

__all__ = ['push_handler']

PUSH_HANDLERS = []


def push_handler(func):
    """
    A decorator to add functions to the push handler.

    Functions decorated with this decorator will be called for any push events
    to the repository. They will be passed ``(repo_handler, git_ref)`` and no
    return values are expected (all actions should happen inside the functions).
    """
    PUSH_HANDLERS.append(func)
    return func


@github_webhook_handler
def handle_pushes(repo_handler, payload, headers):
    """
    Handle push events.
    """

    event = headers['X-GitHub-Event']

    if event not in ('push'):
        return "Not a push event"

    # Get the ref for the push - could be e.g. a branch or a tag
    git_ref = payload['ref']

    # If we are on a branch, make a new repo handler with the correct branch
    if git_ref.startswith('refs/heads/'):
        branch = git_ref.replace('refs/heads/', '')
        repo_handler = RepoHandler(repo_handler.repo, branch,
                                   repo_handler.installation)

    # Get configuration for this plugin
    push_config = repo_handler.get_config_value("pushes", {})
    if not push_config.get("enabled", False):
        return "Skipping commit handlers, disabled in configuration file"

    # Disable if the config is not present
    if push_config is None:
        return

    for function in PUSH_HANDLERS:
        function(repo_handler, git_ref)

    return 'Finished handling push event'
