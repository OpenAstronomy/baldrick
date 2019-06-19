"""Module to handle GitHub API."""
import base64
import re
import requests
import warnings
from datetime import datetime

import dateutil.parser
from flask import current_app
from ttldict import TTLOrderedDict

from baldrick.config import loads
from baldrick.github.github_auth import github_request_headers

__all__ = ['GitHubHandler', 'IssueHandler', 'RepoHandler', 'PullRequestHandler']

HOST = "https://api.github.com"
HOST_NONAPI = "https://github.com"

cfg_cache = TTLOrderedDict(default_ttl=60 * 60)


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

    def get_repo_config(self, branch=None, path_to_file='pyproject.toml',
                        warn_on_failure=True):
        """
        Load configuration from the repository.


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
        cfg : `baldrick.config.Config`
            Configuration parameters.

        """
        # Allow non-existent file but raise error when cannot parse
        try:
            file_content = self.get_file_contents(path_to_file, branch=branch)
            return loads(file_content, tool=current_app.bot_username)
        except Exception as e:
            # Attempt to load the fallback config just in case
            if getattr(current_app, "fall_back_config", None):
                try:
                    return loads(file_content, tool=current_app.fall_back_config)
                except Exception:  # pragma: no cover
                    pass

            if warn_on_failure:
                warnings.warn(str(e))

            # Empty dict means calling code set the default
            repo_config = current_app.conf.copy()

        return repo_config

    def get_config_value(self, cfg_key, cfg_default=None, branch=None):
        """
        Convenience method to extract user configuration values.

        Values are extracted from the repository configuration, and if not
        defined, they are extracted from the global app configuration. If this
        does not exist either, the value is set to the ``cfg_default`` argument.
        """

        global cfg_cache

        cfg_cache_key = (self.repo, branch, self.installation)
        if cfg_cache_key not in cfg_cache:
            cfg_cache[cfg_cache_key] = self.get_repo_config(branch=branch)

        cfg = cfg_cache.get(cfg_cache_key, {})

        config = current_app.conf.get(cfg_key, {}).copy()
        config.update(cfg.get(cfg_key, {}))

        if len(config) > 0:
            return config
        else:
            return cfg_default

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

        commit_hash: str
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

    def list_statuses(self, commit_hash):
        """
        List status messages on a commit on GitHub.

        Parameters
        ----------
        commit_hash : str
            The commit has to get the statuses for
        """

        url = f'{HOST}/repos/{self.repo}/commits/{commit_hash}/statuses'
        results = paged_github_json_request(url, headers=self._headers)

        statuses = {}
        for result in results:
            context = result['context']
            statuses[context] = {'state': result['state'],
                                 'description': result['description'],
                                 'target_url': result.get('target_url')}

        return statuses


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

    def get_file_contents(self, path_to_file, branch=None):
        if branch is None:
            branch = self.branch
        return super().get_file_contents(path_to_file, branch=branch)

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
        data['body'] = body

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

    def set_assignees(self, assignees):
        """Assign the issue to the specified assignee(s)."""

        response = requests.post(self._url_issue, headers=self._headers,
                                 json={'assignees': list(assignees)})

        assert response.ok, response.content

    def add_assignees(self, assignees):
        """Add the specified assignee(s) to the issue."""

        if isinstance(assignees, str): # single assignee passed in
            assignees = [assignees]

        current_assignees = self.json.get('assignees', [])
        return self.set_assignees(current_assignees + list(assignees))

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

    # https://developer.github.com/v3/checks/runs/#create-a-check-run
    def set_check(self, name, summary, commit_hash='head', details_url=None,
                  status='queued', conclusion='neutral'):
        """
        Set check status.

        .. note:: This method does not provide API access to full
                  check run capability (e.g., Markdown text, annotation,
                  image). Add them as needed.

        Parameters
        ----------
        name : str
            Name of the check.

        summary : str
            Summary of the check run.

        commit_hash: { 'head' | 'base' }, optional
            The SHA of the commit.

        details_url : str or `None`, optional
            The URL of the integrator's site that has the full details
            of the check.

        status : { 'queued' | 'in_progress' | 'completed' }
            The current status.

        conclusion : { 'success' | 'failure' | 'neutral' | 'cancelled' | 'timed_out' | 'action_required' }
            The final conclusion of the check.
            Required if you provide a status of ``'completed'``.
            When the conclusion is ``'action_required'``, additional details
            should be provided on the site specified by ``'details_url'``.
            Note: Providing conclusion will automatically set the status
            parameter to ``'completed'``.

        """
        url = f'{HOST}/repos/{self.repo}/check-runs'
        headers = self._headers
        headers['Accept'] = 'application/vnd.github.antiope-preview+json'

        if commit_hash == "head":
            commit_hash = self.head_sha
        elif commit_hash == "base":
            commit_hash = self.base_sha

        tt = datetime.utcnow()
        completed_at = tt.isoformat(timespec='seconds') + 'Z'

        output = {'title': name, 'summary': summary}
        parameters = {'name': name, 'head_sha': commit_hash, 'status': status,
                      'conclusion': conclusion, 'completed_at': completed_at,
                      'output': output}
        if details_url is not None:
            parameters['details_url'] = details_url

        response = requests.post(url, headers=headers, json=parameters)
        assert response.ok, response.content

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

        commit_hash: { 'head' | 'base' }
            The commit hash to set the status on.
            Defaults to "head" can also be "base".

        target_url : str or `None`
            Link to bot comment that is relevant to this status, if given.

        """
        if commit_hash == "head":
            commit_hash = self.head_sha
        elif commit_hash == "base":
            commit_hash = self.base_sha
        super().set_status(state, description, context, commit_hash, target_url)

    def list_statuses(self, commit_hash="head"):
        """
        List status messages on a commit on GitHub.

        Parameters
        ----------
        commit_hash : str, optional
            The commit hash to set the status on. Defaults to "head" can also be "base".
        """
        if commit_hash == "head":
            commit_hash = self.head_sha
        elif commit_hash == "base":
            commit_hash = self.base_sha
        return super().list_statuses(commit_hash)

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

    def get_modified_files(self):
        """Get all the filenames of the files modified by this PR."""
        files = paged_github_json_request(self._url_files,
                                          headers=self._headers)
        return [f['filename'] for f in files]

    def get_file_contents(self, path_to_file, branch=None):
        """
        Get the contents of a file.

        This will get the file from the head branch of the PR by default.
        """
        if not branch:
            branch = self.head_branch
        return super().get_file_contents(path_to_file, branch=branch)

    def get_repo_config(self, branch=None, path_to_file='pyproject.toml',
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
        return super().get_repo_config(branch=branch, path_to_file=path_to_file,
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
