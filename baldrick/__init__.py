import os

from flask import Flask
from werkzeug.contrib.fixers import ProxyFix

from baldrick.blueprints import github, circleci

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

    app.integration_id = int(os.environ['GITHUB_APP_INTEGRATION_ID'])
    app.private_key = os.environ['GITHUB_APP_PRIVATE_KEY']

    app.bot_username = name

    if register_blueprints:
        app.register_blueprint(github)
        app.register_blueprint(circleci)

    @app.route("/")
    def index():
        return "Nothing to see here"

    @app.route("/installation_authorized")
    def installation_authorized():
        return "Installation authorized"

    return app
