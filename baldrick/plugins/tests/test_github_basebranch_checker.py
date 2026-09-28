# For these tests, we patch the repo and pull request handler directly rather
# than the requests to the server, as we assume the repo and pull request
# handlers are tested inside baldrick.

from copy import copy
from unittest.mock import MagicMock

from baldrick.plugins.github_pull_requests import PULL_REQUEST_CHECKS
from baldrick.plugins.github_pull_requests_base_branch import check_base_branch


def setup_module(module):
    # Importing the plugin module above registers check_base_branch in the
    # global PULL_REQUEST_CHECKS registry as an import side effect, so save
    # and remove that registration here to stop it leaking into other test
    # modules when the whole suite is run in a single session.
    module.PULL_REQUEST_CHECKS_ORIG = copy(PULL_REQUEST_CHECKS)
    module.PULL_REQUEST_CHECKS_ORIG.pop(check_base_branch, None)
    PULL_REQUEST_CHECKS.pop(check_base_branch, None)


def teardown_module(module):
    PULL_REQUEST_CHECKS.clear()
    PULL_REQUEST_CHECKS.update(module.PULL_REQUEST_CHECKS_ORIG)


class TestBaseBranchChecker:
    def setup_method(self, method):
        self.labels = []

        self.pr_handler = MagicMock()
        self.pr_handler.number = 1234

        self.repo_handler = MagicMock()
        self.repo_handler.get_config_value.return_value = {"enabled": True}

    def test_good_base(self, app):
        self.pr_handler.base_branch = "main"

        with app.app_context():
            sta = check_base_branch(self.pr_handler, self.repo_handler)

        assert sta["basebranch"]["state"] == "success"

    def test_bad_base(self, app):
        self.pr_handler.base_branch = "stable"

        with app.app_context():
            sta = check_base_branch(self.pr_handler, self.repo_handler)

        assert sta["basebranch"]["state"] == "failure"
