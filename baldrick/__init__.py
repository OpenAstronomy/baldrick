import os

from flask import Flask
from werkzeug.contrib.fixers import ProxyFix

from baldrick.config import load, Config
from baldrick.blueprints import github_blueprint, circleci_blueprint

__all__ = ['create_app']


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

    app = Flask(name)

    app.wsgi_app = ProxyFix(app.wsgi_app)

    # Check if there is a global configuration
    global_toml = os.path.join(os.path.expanduser('~'), 'pyproject.toml')
    if os.path.exists(global_toml):
        app.conf = load(global_toml)
    else:
        app.conf = Config()

    app.integration_id = int(os.environ['GITHUB_APP_INTEGRATION_ID'])
    app.private_key = os.environ['GITHUB_APP_PRIVATE_KEY']

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
