import base64
import requests

from changebot.github_auth import github_request_headers

__all__ = ['RepoHandler', 'PullRequestHandler']

HOST = "https://api.github.com"


class RepoHandler(object):

    def __init__(self, repo, branch, installation):
        self.repo = repo
        self.branch = branch
        self.installation = installation
        self._cache = {}

    def invalidate_cache(self):
        self._cache.clear()

    @property
    def _headers(self):
        return github_request_headers(self.installation)

    @property
    def _url_contents(self):
        return f'{HOST}/repos/{self.repo}/contents/'

    def get_file_contents(self, path_to_file):
        url_file = self._url_contents + path_to_file
        data = {'ref': self.branch}
        response = requests.get(url_file, params=data, headers=self._headers)
        assert response.ok, response.content
        contents_base64 = response.json()['content']
        return base64.b64decode(contents_base64).decode()


class PullRequestHandler(object):

    def __init__(self, repo, number, installation):
        self.repo = repo
        self.number = number
        self.installation = installation
        self._cache = {}

    def invalidate_cache(self):
        self._cache.clear()

    @property
    def _headers(self):
        return github_request_headers(self.installation)

    @property
    def _url_pull_request(self):
        return f'{HOST}/repos/{self.repo}/pulls/{self.number}'

    @property
    def _url_review_comment(self):
        return f'{self._url_pull_request}/reviews'

    @property
    def _url_head_status(self):
        return f'{HOST}/repos/{self.repo}/statuses/{self.head_sha}'

    @property
    def _url_labels(self):
        return f'{HOST}/repos/{self.repo}/issues/{self.number}/labels'

    @property
    def json(self):
        if 'json' not in self._cache:
            response = requests.get(self._url_pull_request, headers=self._headers)
            assert response.ok, response.content
            self._cache['json'] = response.json()
        return self._cache['json']

    @property
    def head_sha(self):
        return self.json['head']['sha']

    @property
    def head_branch(self):
        return self.json['head']['ref']

    @property
    def milestone(self):
        milestone = self.json['milestone']
        if milestone is None:
            return ''
        else:
            return milestone['title']

    @property
    def labels(self):
        response = requests.get(self._url_labels, headers=self._headers)
        assert response.ok, response.content
        return [label['name'] for label in response.json()]

    def submit_review(self, decision, body):
        """
        Submit a review comment to the pull request

        Parameters
        ----------
        decision : { 'approve' | 'request_changes' | 'comment' }
            The decision as to whether to aprove or reject the changes so far.
        body : str
            The body of the review comment
        """

        data = {}
        data['commit_id'] = self.head_sha
        data['body'] = body
        data['event'] = decision.upper()

        response = requests.post(self._url_review_comment, json=data, headers=self._headers)
        assert response.ok, response.content

    def set_status(self, state, description, context):
        """
        Set status message in a pull request on GitHub.

        Parameters
        ----------
        pull_request_payload : dict
            The payload sent from GitHub via the webhook interface.
        state : { 'pending' | 'error' | 'pass' }
            The state to set for the pull request.
        description : str
            The message that appears in the status line.
        context : str
             A string used to identify the status line.
        """

        data = {}
        data['state'] = state
        data['description'] = description
        data['context'] = context

        response = requests.post(self._url_head_status, json=data, headers=self._headers)
        assert response.ok, response.content
