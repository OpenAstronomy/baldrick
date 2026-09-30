"""Module to handle GitHub API."""

import os
from datetime import UTC, datetime

from cachetools import TTLCache
from flask import current_app
from github import Github, GithubException, UnknownObjectException
from github.Commit import Commit
from loguru import logger

from baldrick.config import Config, loads
from baldrick.github.github_auth import get_github

__all__ = ["GitHubHandler", "IssueHandler", "PullRequestHandler", "RepoHandler"]

FILE_CACHE = TTLCache(maxsize=512, ttl=float(os.environ.get("BALDRICK_FILE_CACHE_TTL", 60)))


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
    def _github(self):
        if "github" not in self._cache:
            if self.installation is None:
                self._cache["github"] = Github(lazy=True)
            else:
                self._cache["github"] = get_github(self.installation)
        return self._cache["github"]

    @property
    def _repo(self):
        # This is a lazy object, so no API call is made until an actual
        # request is needed.
        if "repo" not in self._cache:
            self._cache["repo"] = self._github.get_repo(self.repo)
        return self._cache["repo"]

    def _commit(self, commit_hash):
        # Construct a lazy commit seeded with the sha, so that PyGithub
        # methods that need the sha do not have to fetch the commit first.
        url = f"{self._repo.url}/commits/{commit_hash}"
        return Commit(self._github.requester, attributes={"url": url, "sha": commit_hash}, completed=False)

    @property
    def repo_info(self):
        """
        The return of GET /repos/{org}/{repo}
        """
        try:
            return self._repo.raw_data
        except GithubException as exc:
            raise ValueError(f"Unable to fetch repo information {exc.data}") from exc

    @property
    def default_branch(self):
        return self.repo_info["default_branch"]

    def get_file_contents(self, path_to_file, branch=None):
        if branch is None:
            branch = self.default_branch
        cache_key = f"{self.repo}:{path_to_file}@{branch}"

        # TTLCache raises KeyError for expired as well as missing keys, so
        # we access the cache via try/except
        try:
            return FILE_CACHE[cache_key]
        except KeyError:
            pass

        try:
            contents = self._repo.get_contents(path_to_file, ref=branch).decoded_content.decode()
        except UnknownObjectException as exc:
            # A missing branch or ref also results in a 404, and should not
            # be treated in the same way as a missing file
            if exc.data.get("message") != "Not Found":
                raise
            raise FileNotFoundError(f"{self.repo}:{path_to_file}@{branch}") from None

        FILE_CACHE[cache_key] = contents
        return contents

    def get_repo_config(self, branch=None, path_to_file="pyproject.toml"):
        """
        Load configuration from the repository.


        Parameters
        ----------
        branch : `str`
            The branch to read the config file from. (Will default to the default branch)

        path_to_file : `str`
            Path to the ``pyproject.toml`` file in the repository. Will default
            to the root of the repository.

        Returns
        -------
        cfg : `baldrick.config.Config`
            Configuration parameters.

        """
        branch = branch or self.default_branch
        app_config = current_app.conf.copy()
        fallback_config = Config()
        repo_config = Config()

        try:
            file_content = self.get_file_contents(path_to_file, branch=branch)
        except FileNotFoundError:
            logger.debug(f"No config file found in {self.repo}@{branch}.")
            file_content = None

        if file_content:
            repo_config = loads(file_content, tool=current_app.bot_username) or {}
            logger.trace(f"Got the following config from {self.repo}@{branch}: {repo_config}")
            if len(repo_config) == 0:
                logger.exception(
                    f"Failed to load config in {self.repo} on branch {branch}, despite finding a pyproject.toml file."
                )

            if getattr(current_app, "fall_back_config", None):
                fallback_config = loads(file_content, tool=current_app.fall_back_config) or {}
                if len(fallback_config) == 0:
                    logger.trace(f"Didn't find a fallback config in {self.repo}@{branch}.")

        # Priority is 1) repo_config 2) fallback_config 3) app_config
        app_config.update_from_config(fallback_config)
        app_config.update_from_config(repo_config)

        logger.debug(f"Got this combined config from {self.repo}@{branch}: {app_config}")

        return app_config

    def get_config_value(self, cfg_key, cfg_default=None, branch=None):
        """
        Convenience method to extract user configuration values.

        Values are extracted from the repository configuration, and if not
        defined, they are extracted from the global app configuration. If this
        does not exist either, the value is set to the ``cfg_default`` argument.
        """
        cfg = self.get_repo_config(branch=branch)

        config = current_app.conf.get(cfg_key, {}).copy()
        config.update(cfg.get(cfg_key, {}))

        if len(config) > 0:
            return config
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

        kwargs = {}

        if description is not None:
            kwargs["description"] = description

        if context is not None:
            kwargs["context"] = context

        if target_url is not None:
            kwargs["target_url"] = target_url

        self._commit(commit_hash).create_status(state, **kwargs)

    def list_statuses(self, commit_hash):
        """
        List status messages on a commit on GitHub.

        Parameters
        ----------
        commit_hash : str
            The commit has to get the statuses for
        """

        statuses = {}
        for status in self._commit(commit_hash).get_combined_status().statuses:
            statuses[status.context] = {
                "state": status.state,
                "description": status.description,
                "target_url": status.target_url,
            }

        return statuses

    def list_checks(self, commit_hash, only_ours=True):
        """
        List check messages on a commit on GitHub.

        Parameters
        ----------
        commit_hash : str
            The commit has to get the statuses for

        only_ours : `bool`, optional
            Only return status that this app has posted.
        """

        checks = {}
        for check in self._commit(commit_hash).get_check_runs():
            # Skip checks from other apps if specified.
            if only_ours and check.app.id != current_app.integration_id:
                continue

            # These keys match the kwargs to set_check
            checks[check.external_id] = {
                "external_id": check.external_id,
                "title": check.output.title,
                "summary": check.output.summary,
                "name": check.name,
                "text": check.output.text,
                "commit_hash": check.head_sha,
                "details_url": check.details_url,
                "status": check.status,
                "conclusion": check.conclusion,
                "check_id": check.id,
            }

        return checks


class RepoHandler(GitHubHandler):
    def __init__(self, repo, branch=None, installation=None):
        self.branch = branch
        super().__init__(repo, installation=installation)

    def open_pull_requests(self):
        return [pull_request.number for pull_request in self._repo.get_pulls(state="open")]

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
        issues = self._repo.get_issues(state=state, labels=labels.split(","))
        if exclude_pr:
            # Use ._rawData to check for the key, as .raw_data would trigger
            # a separate API call for each issue in the list
            issue_list = [issue.number for issue in issues if "pull_request" not in issue._rawData]
        else:
            issue_list = [issue.number for issue in issues]
        return issue_list

    def get_all_labels(self):
        """Get all label options for this repo"""
        return [label.name for label in self._repo.get_labels()]


class IssueHandler(GitHubHandler):
    def __init__(self, repo, number, installation=None):
        self.number = number
        super().__init__(repo, installation=installation)

    @property
    def _issue(self):
        if "issue" not in self._cache:
            self._cache["issue"] = self._repo.get_issue(int(self.number))
        return self._cache["issue"]

    @property
    def json(self):
        return self._issue.raw_data

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
        last_labeled = None

        for event in self._issue.get_timeline():
            if event.event in ("labeled", "unlabeled") and event._rawData["label"]["name"] == label:
                if event.event == "labeled":
                    last_labeled = event.created_at
                else:
                    last_labeled = None

        if last_labeled is None:
            return None
        return last_labeled.timestamp()

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

        if comment_id is None:
            comment = self._issue.create_comment(body)
        else:
            comment = self._issue.get_comment(int(comment_id))
            comment.edit(body)

        if return_url:
            return comment.html_url
        return None

    def _find_comments(self, login, filter_keep=None):
        if filter_keep is None:

            def filter_keep(message):
                return True

        return [comment for comment in self._issue.get_comments() if filter_keep(comment.body)]

    def find_comments(self, login, filter_keep=None):
        """
        Find comments by a given user.
        """
        comments = self._find_comments(login, filter_keep=filter_keep)
        return [comment.id for comment in comments if comment.user.login == login]

    def last_comment_date(self, login, filter_keep=None):
        """
        Find the last date on which a comment was made.
        """
        comments = self._find_comments(login, filter_keep=filter_keep)
        dates = [comment.created_at for comment in comments if comment.user.login == login]
        if len(dates) > 0:
            return max(dates).timestamp()
        return None

    @property
    def labels(self):
        """Get labels for this issue"""
        return [label.name for label in self._issue.get_labels()]

    # We take this out of set_labels so we can test it without mock
    def _get_missing_labels(self, labels):
        if not isinstance(labels, list):
            labels = [labels]

        # If label already set, do nothing
        missing_labels = set(labels).difference(self.labels)
        if len(missing_labels) == 0:
            return None

        # Need repo handler (default branch)
        if "repohandler" not in self._cache:
            repo = RepoHandler(self.repo, installation=self.installation)
            self._cache["repohandler"] = repo
        else:
            repo = self._cache["repohandler"]

        # If label does not already exist in the repo, give a warning
        repo_labels = repo.get_all_labels()
        nonexistent_labels = missing_labels.difference(repo_labels)
        if len(nonexistent_labels) > 0:
            pass

        # Return labels to be set
        missing_labels = missing_labels.intersection(repo_labels)
        if len(missing_labels) > 0:
            return list(missing_labels)
        return None

    def set_labels(self, labels):
        """Set label(s) to issue"""

        missing_labels = self._get_missing_labels(labels)
        if missing_labels is None:
            return

        self._issue.add_to_labels(*missing_labels)

    def close(self):
        self._issue.edit(state="closed")

    @property
    def is_closed(self):
        """Is the issue closed?"""
        answer = False
        if self.json["state"] == "closed":
            answer = True
        return answer


class PullRequestHandler(IssueHandler):
    @property
    def _pull(self):
        if "pull" not in self._cache:
            self._cache["pull"] = self._repo.get_pull(int(self.number))
        return self._cache["pull"]

    @property
    def json(self):
        return self._pull.raw_data

    # https://developer.github.com/v3/checks/runs/#create-a-check-run
    def set_check(
        self,
        external_id,
        title,
        name=None,
        summary=None,
        text=None,
        commit_hash="head",
        details_url=None,
        status=None,
        conclusion="neutral",
        check_id=None,
        completed_at=None,
    ):
        """
        Set check status.

        .. note:: This method does not provide API access to full
                  check run capability (e.g., annotation and
                  image). Add them as needed.

        Parameters
        ----------
        external_id : `str`
            The internal reference for this check, used to reference the check
            later, to update it.

        title: `str`
            The short description of the check to be put in the status line of the PR.

        name : `str`, optional
            Name of the check, defaults to ``{bot_username}:{external_id}`` if
            not specified, is displayed first in the status line.

        summary : `str`
            Summary of the check run, displays at the top of the checks page.

        text : `str`, optional
            The full body of the check, displayed on the checks page.

        commit_hash: { 'head' | 'base' }, optional
            The SHA of the commit.

        details_url : `str` or `None`, optional
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

        check_id : `int`, optional
            If specified this check will be updated rather than a new check
            being made.

        completed_at : `bool` or `datetime.datetime`
            The time the check completed. If `None` this will not be set, if
            `True` it will be set to the time this method is called, otherwise
            it should be a `datetime.datetime.`

        """
        if commit_hash == "head":
            commit_hash = self.head_sha
        elif commit_hash == "base":
            commit_hash = self.base_sha

        if completed_at is True:
            completed_at = datetime.now(UTC)

        # If name isn't specified revert to external_id
        name = name or f"{current_app.bot_username}:{external_id}"

        output = {"title": title, "summary": summary or ""}
        if text is not None:
            output["text"] = text

        if status == "completed" and conclusion is None:
            logger.warning(
                "When a GitHub check status is completed, conclusion must be specified, setting it to 'neutral'"
            )
            conclusion = "neutral"

        kwargs = {"name": name, "head_sha": commit_hash, "external_id": external_id, "output": output}

        if status is not None:
            kwargs["status"] = status

        if details_url is not None:
            kwargs["details_url"] = details_url

        if conclusion is not None:
            kwargs["conclusion"] = conclusion
            if completed_at is not None:
                kwargs["completed_at"] = completed_at
            # The GitHub API does this automatically, but we do it explicitly
            # here for consistency and for tests!
            kwargs["status"] = "completed"

        logger.trace(f"Sending GitHub check with {kwargs}")

        if not check_id:
            self._repo.create_check_run(**kwargs)
        else:
            self._repo.get_check_run(int(check_id)).edit(**kwargs)

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

    def list_checks(self, commit_hash="head", only_ours=True):
        """
        List checks on a commit on GitHub.

        Parameters
        ----------
        commit_hash : `str`, optional
            The commit hash to set the check on. Defaults to "head" can also be "base".
        only_ours : `bool`, optional
            Only return checks which were posted by this GitHub app.
        """
        if commit_hash == "head":
            commit_hash = self.head_sha
        elif commit_hash == "base":
            commit_hash = self.base_sha
        return super().list_checks(commit_hash, only_ours=only_ours)

    @property
    def user(self):
        return self.json["user"]["login"]

    @property
    def head_repo_name(self):
        return self.json["head"]["repo"]["full_name"]

    @property
    def head_sha(self):
        return self.json["head"]["sha"]

    @property
    def head_branch(self):
        return self.json["head"]["ref"]

    @property
    def base_branch(self):
        return self.json["base"]["ref"]

    @property
    def base_sha(self):
        return self.json["base"]["sha"]

    @property
    def milestone(self):
        milestone = self.json["milestone"]
        if milestone is None:
            return ""
        return milestone["title"]

    @property
    def draft(self):
        return self.json["draft"]

    def get_modified_files(self):
        """Get all the filenames of the files modified by this PR."""
        return [modified_file.filename for modified_file in self._pull.get_files()]

    def get_file_contents(self, path_to_file, branch=None):
        """
        Get the contents of a file.

        This will get the file from the head branch of the PR by default.
        """
        if not branch:
            branch = self.head_branch
        return super().get_file_contents(path_to_file, branch=branch)

    def get_repo_config(self, branch=None, path_to_file="pyproject.toml"):
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

        Returns
        -------
        cfg : dict
            Configuration parameters.

        """
        if not branch:
            branch = self.base_branch
        return super().get_repo_config(branch=branch, path_to_file=path_to_file)

    def has_modified(self, filelist):
        """Check if PR has modified any of the given list of filename(s)."""
        for modified_file in self._pull.get_files():
            if modified_file.filename in filelist:
                return True
        return False

    def submit_review(self, decision, body):
        """
        Submit a review comment to the pull request

        Parameters
        ----------
        decision : { 'approve' | 'request_changes' | 'comment' }
            The decision as to whether to approve or reject the changes so far.
        body : str
            The body of the review comment
        """

        self._pull.create_review(commit=self._commit(self.head_sha), body=body, event=decision.upper())

    @property
    def last_commit_date(self):
        dates = [commit.commit.committer.date for commit in self._pull.get_commits()]
        if len(dates) == 0:
            raise Exception(f"No commits found for pull request {self.number} of {self.repo}")
        return max(dates).timestamp()
