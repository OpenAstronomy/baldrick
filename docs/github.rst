.. _github:

Registering and installing a GitHub app
=======================================

Registering the app
-------------------

Once you have set up the bot on a server (e.g. :ref:`heroku`), you will need to
tell GitHub about the app. To add the bot to your own organization or account,
go to your GitHub organization or account URL (not the repository) and then its
settings. Then, click on "Developer settings" at the very bottom of the left
navigation bar and the "New GitHub App" button on top right.

Give your bot a "GitHub App name" as you want it to appear on GitHub
activities. Under "Homepage URL", enter the GitHub repository URL where
the bot code resides (either here or your fork, as appropriate).

For the **User authorization callback URL**, it should be in the format of
``https://<heroku-bot-name>.herokuapp.com/installation_authorized``.

For the **Webhook URL**, it should be in the format of
``https://<heroku-bot-name>.herokuapp.com/github``.

In the **Webhook secret** field, enter a long random string. baldrick verifies
the signature of every incoming webhook delivery against this secret and
rejects deliveries with a missing or invalid signature, so this must be set.
The same value needs to be set as the ``GITHUB_APP_WEBHOOK_SECRET`` environment
variable on the server running the bot (see :ref:`heroku`). You can ignore
"Setup URL". It would be useful to provide a description of what your bot
intends to do but not required.

Under "Repository permissions", give the app the permissions listed in the
following table. Which ones are needed depends on the plugins you enable (see
:doc:`plugins`), but it is simplest to grant all of them. The **Metadata**
permission is always granted to GitHub apps and does not need to be selected.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Permission
     - Access
     - Needed by
   * - **Contents**
     - Read-only
     - All plugins, to read the bot configuration from ``pyproject.toml``. The
       towncrier changelog checker also uses it to read changelog entries, and
       push handlers need it to receive push events.
   * - **Pull requests**
     - Read and write
     - All pull request handlers, to read pull request details and files and
       to post comments.
   * - **Issues**
     - Read-only
     - All pull request handlers, to receive events when the milestone of a
       pull request changes.
   * - **Checks**
     - Read and write
     - All pull request handlers, to report the results of the checks (for
       example the milestone, towncrier changelog and base branch checkers).
   * - **Commit statuses**
     - Read and write
     - The CircleCI artifacts plugin only, to post the link to the artifacts.

Once you have selected these permissions, extra "Subscribe to events" entries
appear, of which the following are needed:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Event
     - Needed by
   * - **Pull request**
     - All pull request handlers.
   * - **Issues**
     - All pull request handlers, to re-run the checks when the milestone of a
       pull request changes.
   * - **Push**
     - Push handlers.

The CircleCI artifacts plugin does not need any GitHub event, since it is
triggered by CircleCI webhooks instead. Other events (such as **Status** or
**Issue comment**) are ignored by the bot, so there is no need to subscribe
to them.

It is up to you to choose whether you want to allow your GitHub app here to
be installed only on your account or by any user or organization.

Once you have clicked "Create GitHub App" button, you can go back to the app's
"General" settings and upload a logo, which is basically a profile picture
of your bot.

Install the bot
---------------

Go to ``https://github.com/apps/<github-app-name>``. Then, click on the big
green "Install" button. You can choose to install the bot on all or select
repositories under your account or organization. It is recommended to only
install it for select repositories by start typing a repository name and let
auto-completion do the hard work for you (repeat this once per repository). Once
you are done, click "Install".

After a successful installation, you will be taken to a
``https://github.com/settings/installations/<installation-number>`` page.
This page is also accessible from your account or organization settings in
"Applications", specifically under "Installed GitHub Apps".
You can change the installation settings by clicking the "Configure"
button next to the listed app, if desired.
