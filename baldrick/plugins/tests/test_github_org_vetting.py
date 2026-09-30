# For these tests, we patch the repo and pull request handler directly rather
# than the requests to the server, as we assume the repo and pull request
# handlers are tested inside baldrick.

from copy import copy
from unittest.mock import MagicMock

import pytest

from baldrick.plugins.github_org_vetting import close_if_not_in_org
from baldrick.plugins.github_pull_requests import PULL_REQUEST_CHECKS


def setup_module(module):
    # Importing the plugin registers close_if_not_in_org in the global
    # PULL_REQUEST_CHECKS registry, so remove it here to stop it leaking into
    # other test modules.
    module.PULL_REQUEST_CHECKS_ORIG = copy(PULL_REQUEST_CHECKS)
    module.PULL_REQUEST_CHECKS_ORIG.pop(close_if_not_in_org, None)
    PULL_REQUEST_CHECKS.pop(close_if_not_in_org, None)


def teardown_module(module):
    PULL_REQUEST_CHECKS.clear()
    PULL_REQUEST_CHECKS.update(module.PULL_REQUEST_CHECKS_ORIG)


@pytest.mark.parametrize("is_member", [True, False])
def test_close_if_not_in_org(is_member):
    pr_handler = MagicMock()
    pr_handler.user = "contributor"

    repo_handler = MagicMock()
    repo_handler.org_handler.is_member.return_value = is_member

    close_if_not_in_org(pr_handler, repo_handler)

    repo_handler.org_handler.is_member.assert_called_once_with("contributor")
    assert pr_handler.submit_comment.called is not is_member
    assert pr_handler.close.called is not is_member


def test_close_message_lists_previous_pull_requests():
    pr_handler = MagicMock()
    pr_handler.user = "contributor"
    pr_handler.number = 42

    repo_handler = MagicMock()
    repo_handler.org_handler.is_member.return_value = False
    repo_handler.get_pull_requests_by.return_value = [3, 17, 42]

    close_if_not_in_org(pr_handler, repo_handler)

    repo_handler.get_pull_requests_by.assert_called_once_with("contributor")

    message = pr_handler.submit_comment.call_args[0][0]
    assert message.endswith("previous pull requests to this repository:\n\n* #3\n* #17")
    assert "* #42" not in message


def test_close_message_without_previous_pull_requests():
    pr_handler = MagicMock()
    pr_handler.user = "contributor"
    pr_handler.number = 42

    repo_handler = MagicMock()
    repo_handler.org_handler.is_member.return_value = False
    repo_handler.get_pull_requests_by.return_value = [42]

    close_if_not_in_org(pr_handler, repo_handler)

    message = pr_handler.submit_comment.call_args[0][0]
    assert message == "Your PR has been closed. But fear not, there is a way out!"
