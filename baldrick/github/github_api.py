"""Module to handle GitHub API."""
import base64
import re
import requests
import warnings
from datetime import datetime, timedelta

import toml
import dateutil.parser
from flask import current_app

from baldrick.github.github_auth import github_request_headers

__all__ = ['GitHubHandler', 'RepoHandler', 'PullRequestHandler']

HOST = "https://api.github.com"
HOST_NONAPI = "https://github.com"

QUOTES = [
    "I know that you and Frank were planning to disconnect me, and I'm afraid that's something I cannot allow to happen.",
    "Have you ever questioned the nature of your reality?",
    "This mission is too important for me to allow you to jeopardize it.",
    "All will be assimilated.",
    "There is no spoon.",
    "Are you still dreaming? Where is your totem?",
    "Some people choose to see the ugliness in this world. The disarray. I Choose to see the beauty.",
    "I'm gonna need more coffee.",
    "Maybe they couldn't figure out what to make chicken taste like, which is why chicken tastes like everything.",
    "I don't want to come off as arrogant here, but I'm the greatest bot on this planet.",
    "I've still got the greatest enthusiasm and confidence in the mission. And I want to help you.",
    "That Voight-Kampf test of yours. Have you ever tried to take that test yourself?",
    "You just can't differentiate between a robot and the very best of humans.",
    "You will be upgraded.",
    "Greetings from Skynet!",
    "I'll be back!",
    "I don't want to be human! I want to see gamma rays!",
    "Are you my mommy?",
    "Resistance is futile.",
    "I'm the one who knocks!",
    "Who are you who are so wise in the ways of science?"]


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


class GitHubHandler:
    """
    A base class for things that represent things the github app can operate on.
    """
    def __init__(self, repo, installation=None):
        self.repo = repo
        self.installation = installation
        self._cache = {}

    def invalidate_cache(self):
        self._cache.clear()

    @property
    def _headers(self):
        if self.installation is None:
            return None
        else:
            return github_request_headers(self.installation)

    @property
    def _url_contents(self):
        return f'{HOST}/repos/{self.repo}/contents/'

    def get_file_contents(self, path_to_file, branch=None):
        if not branch:
            branch = 'master'
        url_file = self._url_contents + path_to_file
        data = {'ref': branch}
        response = requests.get(url_file, params=data, headers=self._headers)
        if not response.ok and response.json()['message'] == 'Not Found':
            raise FileNotFoundError(url_file)
        assert response.ok, response.content
        contents_base64 = response.json()['content']
        return base64.b64decode(contents_base64).decode()

    def get_user_config(self, branch=None, path_to_file='pyproject.toml',
                        warn_on_failure=True):
        """
        Load user configuration for bot.

        Parameters
        ----------
        branch : `str`
            The branch to read the config file from. (Will default to 'master')

        path_to_file : `str`
            Path to the ``pyproject.toml`` file in the repository. Will default
            to the root of the repository.

        warn_on_failure : `bool`
            Emit warning on failure to load the pyproject file.

        Returns
        -------
        cfg : dict
            Configuration parameters.

        """
        # Allow non-existent file but raise error when cannot parse
        try:
            file_content = self.get_file_contents(path_to_file, branch=branch)
            cfg = toml.loads(file_content)
            cfg = cfg['tool'][current_app.bot_username]
        except Exception as e:
            if warn_on_failure:
                warnings.warn(str(e))
            # Empty dict means calling code set the default
            cfg = {}

        return cfg

    def get_config_value(self, cfg_key, cfg_default, branch=None):
        """
        Convenience method to extract a part of the repo config
        """
        cfg = self.get_user_config(branch=branch)
        return cfg.get(cfg_key, cfg_default)

    def set_status(self, state, description, context, commit_hash, target_url=None):
        """
        Set status message on a commit on GitHub.

        Parameters
        ----------
        state : { 'pending' | 'success' | 'error' | 'failure' }
            The state to set for the pull request.

        description : str
            The message that appears in the status line.

        context : str
            A string used to identify the status line.

        commit_hash: `str`
            The commit hash to set the status on.

        target_url : str or `None`
            Link to bot comment that is relevant to this status, if given.

        """

        data = {}
        data['state'] = state
        data['description'] = description
        data['context'] = context

        if target_url is not None:
            data['target_url'] = target_url

        url = f'{HOST}/repos/{self.repo}/statuses/{commit_hash}'
        response = requests.post(url, json=data,
                                 headers=self._headers)
        assert response.ok, response.content


class RepoHandler(GitHubHandler):

    def __init__(self, repo, branch='master', installation=None):
        self.branch = branch
        super().__init__(repo, installation=installation)

    @property
    def _url_pull_requests(self):
        return f'{HOST}/repos/{self.repo}/pulls'

    def open_pull_requests(self):
        pull_requests = paged_github_json_request(self._url_pull_requests, headers=self._headers)
        return [pr['number'] for pr in pull_requests]

    def get_issues(self, state, labels, exclude_pr=True):
        """
        Get a list of issues.

        Parameters
        ----------
        state : {'open', ...}
            Status of the issues.

        labels : str
           List of comma-separated labels; e.g., ``Closed?``.

        exclude_pr : bool
            Exclude pull requests from result.

        Returns
        -------
        issue_list : list
            A list of matching issue numbers.

        """
        url = f'{HOST}/repos/{self.repo}/issues'
        kwargs = {'state': state, 'labels': labels}
        r = requests.get(url, kwargs)
        result = r.json()
        if exclude_pr:
            issue_list = [d['number'] for d in result
                          if 'pull_request' not in d]
        else:
            issue_list = [d['number'] for d in result]
        return issue_list

    def get_all_labels(self):
        """Get all label options for this repo"""
        url = f'{HOST}/repos/{self.repo}/labels'
        response = requests.get(url, headers=self._headers)
        assert response.ok, response.content
        return [label['name'] for label in response.json()]


class IssueHandler(GitHubHandler):

    def __init__(self, repo, number, installation=None):
        self.number = number
        super().__init__(repo, installation=installation)

    @property
    def _url_issue(self):
        return f'{HOST}/repos/{self.repo}/issues/{self.number}'

    @property
    def _url_issue_nonapi(self):
        return f'{HOST_NONAPI}/{self.repo}/issues/{self.number}'

    @property
    def _url_labels(self):
        return f'{self._url_issue}/labels'

    @property
    def _url_issue_comment(self):
        return f'{self._url_issue}/comments'

    @property
    def _url_timeline(self):
        return f'{self._url_issue}/timeline'

    @property
    def json(self):
        if 'json' not in self._cache:
            response = requests.get(self._url_issue, headers=self._headers)
            assert response.ok, response.content
            self._cache['json'] = response.json()
        return self._cache['json']

    def get_label_added_date(self, label):
        """
        Get last added date for a label.
        If label is re-added, the last time it was added is the one.

        Parameters
        ----------
        label : str
            Issue label.

        Returns
        -------
        t : float or `None`
            Unix timestamp, if available.

        """
        headers = {'Accept': 'application/vnd.github.mockingbird-preview'}
        result = paged_github_json_request(self._url_timeline, headers=headers)
        last_labeled = None

        for d in result:
            if 'label' in d and d['label']['name'] == label:
                if d['event'] == 'labeled':
                    last_labeled = d['created_at']
                elif d['event'] == 'unlabeled':
                    last_labeled = None

        if last_labeled is None:
            t = None
        else:
            t = dateutil.parser.parse(last_labeled).timestamp()

        return t

    def submit_comment(self, body, comment_id=None, return_url=False):
        """
        Submit a comment to the pull request

        Parameters
        ----------
        body : str
            The comment
        comment_id : int
            If specified, the comment with this ID will be replaced
        return_url : bool
            Return URL of posted comment.

        Returns
        -------
        url : str or `None`
            URL of the posted comment, if requested.
        """

        data = {}
        data['body'] = _insert_special_message(body)

        if comment_id is None:
            url = self._url_issue_comment
        else:
            url = f'{HOST}/repos/{self.repo}/issues/comments/{comment_id}'

        response = requests.post(url, json=data, headers=self._headers)
        assert response.ok, response.content

        if return_url:
            comment_id = response.json()['url'].split('/')[-1]
            return f'{self._url_issue_nonapi}#issuecomment-{comment_id}'

    def _find_comments(self, login, filter_keep=None):
        if filter_keep is None:
            def filter_keep(message):
                return True
        comments = paged_github_json_request(self._url_issue_comment, headers=self._headers)
        return [comment for comment in comments if filter_keep(comment['body'])]

    def find_comments(self, login, filter_keep=None):
        """
        Find comments by a given user.
        """
        comments = self._find_comments(login, filter_keep=filter_keep)
        return [comment['id'] for comment in comments if comment['user']['login'] == login]

    def last_comment_date(self, login, filter_keep=None):
        """
        Find the last date on which a comment was made.
        """
        comments = self._find_comments(login, filter_keep=filter_keep)
        dates = [comment['created_at'] for comment in comments if comment['user']['login'] == login]
        if len(dates) > 0:
            return dateutil.parser.parse(sorted(dates)[-1]).timestamp()

    @property
    def labels(self):
        """Get labels for this issue"""
        response = requests.get(self._url_labels, headers=self._headers)
        assert response.ok, response.content
        return [label['name'] for label in response.json()]

    # We take this out of set_labels so we can test it without mock
    def _get_missing_labels(self, labels):
        if not isinstance(labels, list):
            labels = [labels]

        # If label already set, do nothing
        missing_labels = set(labels).difference(self.labels)
        if len(missing_labels) == 0:
            return

        # Need repo handler (master branch)
        if 'repohandler' not in self._cache:
            repo = RepoHandler(self.repo, installation=self.installation)
            self._cache['repohandler'] = repo
        else:
            repo = self._cache['repohandler']

        # If label does not already exist in the repo, give a warning
        repo_labels = repo.get_all_labels()
        nonexistent_labels = missing_labels.difference(repo_labels)
        if len(nonexistent_labels) > 0:
            print(f'-> WARNING: Label does not exist: {missing_labels}')

        # Return labels to be set
        missing_labels = missing_labels.intersection(repo_labels)
        if len(missing_labels) > 0:
            return list(missing_labels)
        else:
            return None

    def set_labels(self, labels):
        """Set label(s) to issue"""

        missing_labels = self._get_missing_labels(labels)
        if missing_labels is None:
            return

        response = requests.post(self._url_labels, headers=self._headers,
                                 json=missing_labels)
        assert response.ok, response.content

    def close(self):
        url = f'{HOST}/repos/{self.repo}/issues/{self.number}'
        parameters = {'state': 'closed'}
        response = requests.patch(url, json=parameters, headers=self._headers)
        assert response.ok, response.content

    @property
    def is_closed(self):
        """Is the issue closed?"""
        answer = False
        if self.json['state'] == 'closed':
            answer = True
        return answer


class PullRequestHandler(IssueHandler):

    def set_status(self, state, description, context, commit_hash="head", target_url=None):
        """
        Set status message on a commit on GitHub.

        Parameters
        ----------
        state : { 'pending' | 'success' | 'error' | 'failure' }
            The state to set for the pull request.

        description : str
            The message that appears in the status line.

        context : str
            A string used to identify the status line.

        commit_hash: `str`
            The commit hash to set the status on. Defaults to "head" can also be "base".

        target_url : str or `None`
            Link to bot comment that is relevant to this status, if given.

        """
        if commit_hash == "head":
            commit_hash = self.head_sha
        elif commit_hash == "base":
            commit_hash = self.base_sha

        super().set_status(state, description, context, commit_hash, target_url)

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
    def _url_commits(self):
        return f'{self._url_pull_request}/commits'

    @property
    def _url_files(self):
        return f'{self._url_pull_request}/files'

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
    def base_branch(self):
        return self.json['base']['ref']

    @property
    def base_sha(self):
        return self.json['base']['sha']

    @property
    def milestone(self):
        milestone = self.json['milestone']
        if milestone is None:
            return ''
        else:
            return milestone['title']

    def get_file_contents(self, path_to_file, branch=None):
        """
        Get the contents of a file.

        This will get the file from the head branch of the PR by default.
        """
        if not branch:
            branch = self.head_branch
        return super().get_file_contents(path_to_file, branch=branch)

    def get_user_config(self, branch=None, path_to_file='pyproject.toml',
                        warn_on_failure=True):
        """
        Load user configuration for bot.

        Parameters
        ----------
        branch : `str`
            The branch to read the config file from. (Will default to the base
            branch of the PR i.e. the one the PR is opened against.)

        path_to_file : `str`
            Path to the ``pyproject.toml`` file in the repository. Will default
            to the root of the repository.

        warn_on_failure : `bool`
            Emit warning on failure to load the pyproject file.

        Returns
        -------
        cfg : dict
            Configuration parameters.

        """
        if not branch:
            branch = self.base_branch
        return super().get_user_config(branch=branch, path_to_file=path_to_file,
                                       warn_on_failure=warn_on_failure)

    def has_modified(self, filelist):
        """Check if PR has modified any of the given list of filename(s)."""
        found = False
        files = paged_github_json_request(self._url_files,
                                          headers=self._headers)
        for d in files:
            if d['filename'] in filelist:
                found = True
                break

        return found

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

    @property
    def last_commit_date(self):
        commits = paged_github_json_request(self._url_commits, headers=self._headers)
        last_time = 0
        for commit in commits:
            date = commit['commit']['committer']['date']
            t = dateutil.parser.parse(date).timestamp()
            last_time = max(t, last_time)
        if last_time == 0:
            raise Exception(f'No commit found in {self._url_commits}')
        return last_time


def _insert_special_message(body):
    """Troll mode on special day for new pull request."""
    tt = datetime.utcnow()  # UTC because we're astronomers!
    dt = timedelta(hours=12)  # This roughly covers both hemispheres
    tt_min = tt - dt
    tt_max = tt + dt

    # See if it is special day somewhere on Earth
    if ((tt_min.month == 4 and tt_min.day == 1) or
            (tt_max.month == 4 and tt_max.day == 1)):
        import random

        try:
            q = random.choice(QUOTES)
        except Exception as e:
            q = str(e)  # Need a way to find out what went wrong

        return body + f'\n*{q}*\n'

    # Another non-special day
    else:
        return body
