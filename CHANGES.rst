0.3 (unreleased)
----------------

* New API to post checks on GitHub. [#45]

* Remove support for ``post_pr_comment`` - instead we now support exclusively
  status checks. [#49]

* Added support for custom actions on push. [#53]

* Improve logic for closing stale issues. [#69]

* Removed leftover ``autoclose_stale_pull_request`` configuration item for
  the stale pull request script.

* The ``pull_request_handler`` decorator now accepts a list of actions to
  trigger on. By default, functions decorated ``pull_request_handler`` are
  called with any of unlabeled, labeled, synchronize, opened, milestoned, and
  demilestoned. [#77]

* Added ``check_base_branch`` plugin to make sure that a new pull request
  is opened against the correct upstream base branch (e.g., ``master``). [#92]

* Default branch is now ``main`` in ``github_api.py`` but this should not
  affect existing scripts or plugins unless they fallback to that default.
  [#114]

0.2 (2018-11-22)
----------------

* Make sure that when switching from single- to multi-status, we set any
  previous single checks to success, and edit previous comments. [#37]

* Fix an issue with RepoHandler.get_file_contents when the branch was not
  set to 'master'. [#37]

* Always post new status results, don't try and skip based on existing
  statuses. [#37]

0.1 (2018-11-22)
----------------

* Initial version
