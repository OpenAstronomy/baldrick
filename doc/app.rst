Getting started with building your bot
======================================

We provide a simple template for the files needed to set up your bot at
https://github.com/OpenAstronomy/baldrick/tree/master/template. We take a look
here at the minimal set of files required:

run.py
------

This is the main file that defines how you want your bot to behave. First, set
up the bot using::

    from baldrick import create_app
    app = create_app('<your-bot-name>')

Then, optionally import any plugins you want to have available, including custom
plugins if you have developed any additional ones. The available plugins are::

    import baldrick.plugins.circleci_artifacts
    import baldrick.plugins.github_milestones
    import baldrick.plugins.github_pull_requests
    import baldrick.plugins.github_towncrier_changelog

And finally use the following to start up the bot::

    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

pyproject.toml
--------------

This file can be used to enable/disable any of the plugins that are available
by default. See :doc:`plugins` for more details.

Procfile
--------

This should simply contain::

    web: python -m run

and shouldn't need to be modified further.

runtime.txt
-----------

This file specifies the Python runtime to use for your bot, for example::

    python-3.6.5

Note that this should be Python 3.6 or later.

requirements.txt
----------------

This provides a list of packages required for your bot, and should include at
the very least::

    baldrick

Other files
-----------

Of course, don't forget to include a README file and a LICENSE!
