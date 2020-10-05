# For these tests, we patch the repo and pull request handler directly rather
# than the requests to the server, as we assume the repo and pull request
# handlers are tested inside baldrick.

from unittest.mock import MagicMock

from baldrick.plugins.github_pull_requests_base_branch import check_base_branch


class TestBaseBranchChecker:
    def setup_method(self, method):
        self.labels = []

        self.pr_handler = MagicMock()
        self.pr_handler.number = 1234

        self.repo_handler = MagicMock()

    def test_good_base(self, app):
        self.pr_handler.base_branch = 'master'

        with app.app_context():
            sta = check_base_branch(self.pr_handler, self.repo_handler)

        sta['basebranch']['state'] == 'success'

    def test_bad_base(self, app):
        self.pr_handler.base_branch = 'stable'

        with app.app_context():
            sta = check_base_branch(self.pr_handler, self.repo_handler)

        sta['basebranch']['state'] == 'failure'
