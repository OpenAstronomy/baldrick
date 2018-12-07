0.3 (unreleased)
----------------

* New API to post checks on GitHub. [#45]

* Remove support for ``post_pr_comment`` - instead we now support exclusively
  status checks. [#49]

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
