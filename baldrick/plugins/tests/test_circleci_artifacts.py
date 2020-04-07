import logging
from unittest.mock import patch, call

from baldrick.github.github_api import FILE_CACHE
from baldrick.github.github_api import RepoHandler
from baldrick.plugins.circleci_artifacts import set_commit_status_for_artifacts

CONFIG_TEMPLATE = """
[ tool.testbot ]
[ tool.testbot.circleci_artifacts ]
enabled={enabled}
"""

CONFIG_TEMPLATE_ARTIFACT = """
[ tool.testbot ]
    [ tool.testbot.circleci_artifacts ]
    enabled = true
    [ tool.testbot.circleci_artifacts.docs ]
        url = "raw-test-output/go-test-report.xml"
        message = "Click details to preview the HTML documentation."
"""

CONFIG_TEMPLATE_ARTIFACT_2 = """
[ tool.testbot ]
    [ tool.testbot.circleci_artifacts ]
    enabled = true
    [ tool.testbot.circleci_artifacts.docs ]
        url = "go-test-report.xml"
        message = "Click details to preview the HTML documentation."
    [ tool.testbot.circleci_artifacts.other ]
        url = "go-test.out"
        message = "Something else"
        report_on_fail = true
"""


class TestArtifactPlugin:
    def setup_method(self, method):
        self.get_file_contents_mock = patch(
            'baldrick.github.github_api.GitHubHandler.get_file_contents')

        self.set_status_mock = patch('baldrick.github.github_api.RepoHandler.set_status')
        self.set_status = self.set_status_mock.start()

        self.get_artifacts_mock = patch(
            'baldrick.plugins.circleci_artifacts.get_artifacts_from_build')
        self.get_artifacts = self.get_artifacts_mock.start()
        self.get_artifacts.return_value = []

        self.repo_handler = RepoHandler("nota/repo", "1234")
        self.get_file_contents = self.get_file_contents_mock.start()
        FILE_CACHE.clear()

        self.set_status_mock = patch(
            'baldrick.github.github_api.RepoHandler.set_status')
        self.set_status = self.set_status_mock.start()

    def teardown_method(self, method):
        self.get_file_contents_mock.stop()

    def basic_payload(self):
        return {
            'vcs_revision': '2.0',
            'username': 'test',
            'reponame': 'testbot',
            'status': 'success',
            'build_num': '12356'
        }

    def test_skip(self, app):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled="false")
        with app.app_context():
            set_commit_status_for_artifacts(self.repo_handler, self.basic_payload(), {})

        assert self.set_status.call_count == 0

    def test_no_artifact(self, app):
        self.get_file_contents.return_value = CONFIG_TEMPLATE.format(enabled="true")
        with app.app_context():
            set_commit_status_for_artifacts(self.repo_handler, self.basic_payload(), {})

        assert self.set_status.call_count == 0
        assert self.get_artifacts.call_count == 1

    def test_artifacts(self, app, caplog):
        self.get_file_contents.return_value = CONFIG_TEMPLATE_ARTIFACT_2
        self.get_artifacts.return_value = [
            {
                "path": "raw-test-output/go-test-report.xml",
                "pretty_path": "raw-test-output/go-test-report.xml",
                "node_index": 0,
                "url":
                "https://24-88881093-gh.circle-artifacts.com/0/raw-test-output/go-test-report.xml"
            },
            {
                "path": "raw-test-output/go-test.out",
                "pretty_path": "raw-test-output/go-test.out",
                "node_index": 0,
                "url": "https://24-88881093-gh.circle-artifacts.com/0/raw-test-output/go-test.out"
            }
        ]

        with app.app_context():
            with caplog.at_level(logging.DEBUG):
                set_commit_status_for_artifacts(self.repo_handler, self.basic_payload(), {})

        circle_records = [r for r in caplog.records if r.name == 'baldrick.plugins.circleci_artifacts']
        assert len(circle_records) == 3
        assert "test/testbot" in caplog.text
        assert "https://24-88881093-gh.circle-artifacts.com/0/raw-test-output/go-test-report.xml" in caplog.text
        assert "https://24-88881093-gh.circle-artifacts.com/0/raw-test-output/go-test.out" in caplog.text

        args = [call('success', 'Click details to preview the HTML documentation.',
                     'docs', '2.0',
                     'https://24-88881093-gh.circle-artifacts.com/0/raw-test-output/go-test-report.xml'),
                call('success', 'Something else',
                     'other', '2.0',
                     'https://24-88881093-gh.circle-artifacts.com/0/raw-test-output/go-test.out')]

        self.set_status.call_args_list == args
        assert self.get_artifacts.call_count == 1

    def test_report_on_fail(self, app, caplog):
        self.get_file_contents.return_value = CONFIG_TEMPLATE_ARTIFACT_2
        self.get_artifacts.return_value = [
            {
                "path": "raw-test-output/go-test-report.xml",
                "pretty_path": "raw-test-output/go-test-report.xml",
                "node_index": 0,
                "url":
                "https://24-88881093-gh.circle-artifacts.com/0/raw-test-output/go-test-report.xml"
            },
            {
                "path": "raw-test-output/go-test.out",
                "pretty_path": "raw-test-output/go-test.out",
                "node_index": 0,
                "url": "https://24-88881093-gh.circle-artifacts.com/0/raw-test-output/go-test.out"
            }
        ]

        payload = self.basic_payload()
        payload['status'] = "cancelled"

        with app.app_context():
            with caplog.at_level(logging.DEBUG):
                set_commit_status_for_artifacts(self.repo_handler, payload, {})

        self.set_status.assert_called_once_with('success',
                                                'Something else',
                                                'other',
                                                '2.0',
                                                'https://24-88881093-gh.circle-artifacts.com/0/raw-test-output/go-test.out')
