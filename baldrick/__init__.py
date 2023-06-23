import os

from loguru import logger

from baldrick import github
from baldrick.github import github_auth  # noqa

__all__ = ['create_app', '__version__']

__version__ = '0.3.dev0'

GLOBAL_TOML = ''


def _init_global_toml():
    import os
    global GLOBAL_TOML

    GLOBAL_TOML = os.path.join('.', 'pyproject.toml')


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
    import baldrick.logging  # noqa

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
    if os.path.exists(GLOBAL_TOML):
        conf = load(GLOBAL_TOML, tool=name)
        if conf:
            app.conf = conf

    app.integration_id = int(os.environ['GITHUB_APP_INTEGRATION_ID'])
    app.private_key = os.environ['GITHUB_APP_PRIVATE_KEY']

    try:
        repos = github_auth.repo_to_installation_id_mapping()
    except Exception as e:
        logger.exception("Failed to auth with GitHub")
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
