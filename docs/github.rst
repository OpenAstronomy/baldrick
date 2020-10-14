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
``http://<heroku-bot-name>.herokuapp.com/installation_authorized``.

For the **Webhook URL**, it should be in the format of
``http://<heroku-bot-name>.herokuapp.com/github``.

You can ignore "Setup URL" and "Webhook secret". It would be useful to
provide a description of what your bot intends to do but not required.

The permissions of the app should be read/write access to **Commit statuses**,
**Issues**, and **Pull requests**. Once you have checked these options,
you will see extra "Subscribe to events" entries that you can check as well.
For the events, it should be sufficient to only check **Status**,
**Issue comment**, **Issues**, **Pull request**, **Pull request review**,
and **Pull request review comment**.

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

After a successfull installation, you will be taken to a
``https://github.com/settings/installations/<installation-number>`` page.
This page is also accessible from your account or organization settings in
"Applications", specifically under "Installed GitHub Apps".
You can change the installation settings by clicking the "Configure"
button next to the listed app, if desired.
