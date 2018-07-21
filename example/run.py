import os

from baldrick import create_app


"""
Configure the App
"""

app = create_app('sunpy-bot')


"""
Configure Plugins
"""

# Register the circleci artifact checker
import baldrick.plugins.artifact_checker  # noqa
import baldrick.plugins.milestone_checker  # noqa
import baldrick.plugins.towncrier_changelog_checker  # noqa


# Bind to PORT if defined, otherwise default to 5000.
port = int(os.environ.get('PORT', 5000))
app.run(host='0.0.0.0', port=port, debug=False)
