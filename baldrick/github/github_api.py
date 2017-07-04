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
        if not response.ok and response.json()['message'] == 'Not Found':
            raise FileNotFoundError(path_to_file)
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
    def _url_issue_comment(self):
        return f'{HOST}/repos/{self.repo}/issues/{self.number}/comments'

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
    def user(self):
        return self.json['user']['login']

    @property
    def head_repo_name(self):
        return self.json['head']['repo']['full_name']

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
        state : { 'pending' | 'success' | 'error' | 'failure' }
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

    def find_comments(self, login):
        """
        Find comments by a given user.
        """

        response = requests.get(self._url_issue_comment, headers=self._headers)
        assert response.ok, response.content

        return [comment['id'] for comment in response.json() if comment['user']['login'] == login]

    def submit_comment(self, body, comment_id=None):
        """
        Submit a comment to the pull request

        Parameters
        ----------
        message : str
            The comment
        id : int
            If specified, the comment with this ID will be replaced
        """

        data = {}
        data['body'] = body

        if comment_id is None:
            url = self._url_issue_comment
        else:
            url = f'{HOST}/repos/{self.repo}/issues/comments/{comment_id}'

        response = requests.post(url, json=data, headers=self._headers)
        assert response.ok, response.content
