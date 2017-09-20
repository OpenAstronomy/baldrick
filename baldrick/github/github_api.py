import re
import base64
import requests
from copy import deepcopy

import dateutil.parser

from changebot.github_auth import github_request_headers

__all__ = ['RepoHandler', 'PullRequestHandler']

HOST = "https://api.github.com"


def paged_github_json_request(url, headers=None):

    response = requests.get(url, headers=headers)
    assert response.ok, response.content
    results = response.json()

    if 'Link' in response.headers:

        links = response.headers['Link']

        # There are likely better ways to parse/extract the link information
        # but here we just find the last page number mentioned in the header
        # 'Link' section and then loop over all pages to get the comments
        last_match = list(re.finditer('page=[0-9]+', links))[-1]
        last_page = int(links[last_match.start():last_match.end()].split('=')[1])

        # If there are other pages, just loop over them and get all the
        # comments
        if last_page > 1:
            for page in range(2, last_page + 1):
                response = requests.get(url + '?page={0}'.format(page), headers=headers)
                assert response.ok, response.content
                results += response.json()

    return results


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

    @property
    def _url_pull_requests(self):
        return f'{HOST}/repos/{self.repo}/issues/{self.number}/labels'

    def open_pull_requests(self, repo):
        response = requests.get(self._url_pull_requests, headers=self._headers)
        assert response.ok, response.content
        return [pr['number'] for pr in response.json()]

    def get_file_contents(self, path_to_file):
        url_file = self._url_contents + path_to_file
        data = {'ref': self.branch}
        response = requests.get(url_file, params=data, headers=self._headers)
        assert response.ok, response.content
        contents_base64 = response.json()['content']
        return base64.b64decode(contents_base64).decode()

    def get_issues(self, state, labels):
        # RETURN LIST OF ISSUE IDs
        return


class IssueHandler(object):

    def __init__(self, repo, number, installation):
        self.repo = repo
        self.number = number
        self.installation = installation
        self._cache = {}

    @property
    def _headers(self):
        if self.installation is None:
            return None
        else:
            return github_request_headers(self.installation)

    def invalidate_cache(self):
        self._cache.clear()

    @property
    def _url_labels(self):
        return f'{HOST}/repos/{self.repo}/issues/{self.number}/labels'

    @property
    def _url_issue_comment(self):
        return f'{HOST}/repos/{self.repo}/issues/{self.number}/comments'

    def get_label_added_date(self, label):
        # RETURN datetime object
        return

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

    def find_comments(self, login):
        """
        Find comments by a given user.
        """
        comments = paged_github_json_request(self._url_issue_comment, headers=self._headers)
        return [comment['id'] for comment in comments if comment['user']['login'] == login]

    @property
    def labels(self):
        response = requests.get(self._url_labels, headers=self._headers)
        assert response.ok, response.content
        return [label['name'] for label in response.json()]


class PullRequestHandler(IssueHandler):

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
    def _url_timeline(self):
        return f'https://api.github.com/repos/{self.repo}/issues/{self.number}/timeline'

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

    def get_last_commit_date(self):
        # RETURN datetime object
        return

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

    @property
    def last_commit_date(self):
        if self._headers is None:
            headers = {}
        else:
            headers = deepcopy(self._headers)
        headers['Accept'] = 'application/vnd.github.mockingbird-preview'
        events = paged_github_json_request(self._url_timeline, headers=headers)
        date = None
        print(events)
        for event in events:
            if event['event'] == 'committed':
                date = event['committer']['date']
        if date is None:
            raise Exception(f'No commit found in {url}')
        return dateutil.parser.parse(date).timestamp()
