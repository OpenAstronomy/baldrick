import os
from pathlib import Path

from loguru import logger

from baldrick import github
from baldrick.github import github_auth

__all__ = ["__version__", "create_app"]

__version__ = "0.3.dev0"

GLOBAL_TOML = ""


def _init_global_toml():
    global GLOBAL_TOML

    GLOBAL_TOML = Path("pyproject.toml")


def _allow_unverified_webhooks():
    return os.environ.get("BALDRICK_ALLOW_UNVERIFIED_WEBHOOKS", "").lower() in ("1", "true", "yes", "on")


def _validate_startup_environment():
    """
    Check that the environment variables required to run a baldrick bot are
    set and valid, raising an informative exception if not.
    """
    problems = []

    integration_id = os.environ.get("GITHUB_APP_INTEGRATION_ID")
    if not integration_id:
        problems.append("GITHUB_APP_INTEGRATION_ID is not set (the numeric ID of the GitHub App).")
    else:
        try:
            int(integration_id)
        except ValueError:
            problems.append(f"GITHUB_APP_INTEGRATION_ID must be an integer (got {integration_id!r}).")

    if not os.environ.get("GITHUB_APP_PRIVATE_KEY"):
        problems.append("GITHUB_APP_PRIVATE_KEY is not set (the PEM private key of the GitHub App).")

    if not os.environ.get("GITHUB_APP_WEBHOOK_SECRET"):
        if _allow_unverified_webhooks():
            logger.warning(
                "BALDRICK_ALLOW_UNVERIFIED_WEBHOOKS is set: incoming GitHub "
                "webhooks will not be verified. Only use this for local "
                "development and testing."
            )
        else:
            problems.append(
                "GITHUB_APP_WEBHOOK_SECRET is not set. Set it to the same "
                'value as the "Webhook secret" field in the General settings '
                "of your GitHub App (https://github.com/settings/apps) so "
                "that incoming webhooks can be verified. For local "
                "development and testing only, set "
                "BALDRICK_ALLOW_UNVERIFIED_WEBHOOKS=1 to allow unverified "
                "webhooks instead."
            )

    if problems:
        raise RuntimeError(
            "baldrick cannot start because of the following problems with "
            "the environment:\n\n  - " + "\n  - ".join(problems)
        )


def create_app(name, register_blueprints=True):
    """
    Create a flask app based on Baldrick.

    Parameters
    ----------
    name : `str`
        The name to be passed to ``Flask``. This will also be used as the bot
        user name. This can be overridden with ``app.bot_username``.

    register_blueprints : `bool`
        Register the default blueprints included with Baldrick.

    Returns
    -------
    app

    """
    # Setup loguru integration, must be run before import flask.
    import baldrick.logging

    from flask import Flask

    try:
        from werkzeug.middleware.proxy_fix import ProxyFix
    except ImportError:
        from werkzeug.contrib.fixers import ProxyFix

    from baldrick.config import load, Config
    from baldrick.blueprints import github_blueprint, circleci_blueprint

    app = Flask(name)

    app.wsgi_app = ProxyFix(app.wsgi_app)

    # Check if there is a global configuration
    app.conf = Config()
    if Path(GLOBAL_TOML).exists():
        conf = load(GLOBAL_TOML, tool=name)
        if conf:
            app.conf = conf

    _validate_startup_environment()

    app.integration_id = int(os.environ["GITHUB_APP_INTEGRATION_ID"])
    app.private_key = os.environ["GITHUB_APP_PRIVATE_KEY"]
    app.webhook_secret = os.environ.get("GITHUB_APP_WEBHOOK_SECRET")
    app.allow_unverified_webhooks = _allow_unverified_webhooks()

    try:
        repos = github_auth.repo_to_installation_id_mapping()
    except Exception:
        logger.exception("Failed to auth with GitHub")
        raise
    else:
        logger.info(f"Installed on the following repos {repos}")

    app.bot_username = name

    if register_blueprints:
        app.register_blueprint(github_blueprint)
        app.register_blueprint(circleci_blueprint)

    @app.route("/")
    def index():
        return "Nothing to see here"

    @app.route("/installation_authorized")
    def installation_authorized():
        return "Installation authorized"

    return app


_init_global_toml()
