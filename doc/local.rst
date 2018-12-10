Trying out components of the bot locally
========================================

GitHub API
----------

The different components of the bot interact with GitHub via a set of helper
classes that live in ``baldrick.github``. These classes are
:class:`~baldrick.github.RepoHandler`,
:class:`~baldrick.github.IssueHandler`, and
:class:`~baldrick.github.PullRequestHandler`. It is possible to try
these out locally, at least for the parts of the GitHub API that do not require
authentication. For example, the following should work::

    >>> from baldrick.github import RepoHandler, IssueHandler, PullRequestHandler
    >>> repo = RepoHandler('astropy/astropy')
    >>> repo.get_issues('open', 'Close?')
    [6025, 5193, 4842, 4549, 4058, 3951, 3845, 2603, 2232, 1920, 1024, 435, 383, 282]
    >>> issue = IssueHandler('astropy/astropy', 6597)
    >>> issue.labels
    ['Bug', 'coordinates']
    >>> pr = PullRequestHandler('astropy/astropy', 6606)
    >>> pr.labels
    ['Enhancement', 'Refactoring', 'testing', 'Work in progress']
    >>> pr.last_commit_date
    1506374526.0

However since these are being run un-authenticated, you may quickly run into
the GitHub public API limits. If you are interested in authenticating locally,
see the `Authenticating locally`_ section below.

Authenticating locally
----------------------

In some cases, you may want to test the bot locally as if it was running on
Heroku. In order to do this you will need to make sure you have all the
environment variables described above set correctly.

The main ones to get right as far as authentication is concerned are as
follows (see :doc:`heroku` for further details):

* ``GITHUB_APP_INTEGRATION_ID``
* ``GITHUB_APP_PRIVATE_KEY``

The last thing you will need is an **Installation ID** - a GitHub app can be
linked to different GitHub accounts, and for each account or organization, it
has a unique ID. You can find out this ID by going to **Your installations** and
then clicking on the settings box next to the account where you have a test
repository you want to interact with. The URL of the page you go to will contain
the Installation ID and look like:

    https://github.com/settings/installations/36238

In this case, 36238 is the installation ID. Provided you set the environment
variables correctly, you should then be able to do e.g.::

    >>> from baldrick.github import IssueHandler
    >>> issue = IssueHandler('astrofrog/test-bot', 5, installation=36238)
    >>> issue.submit_comment('I am alive!')

.. note:: Authentication will not work properly if you have a ``.netrc`` file
          in your home directory, so you will need to rename this file
          temporarily.
