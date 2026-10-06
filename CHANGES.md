## v0.3 - 2026-06-03

### What's Changed
* commit_hash docstring formatting by @pllim in https://github.com/OpenAstronomy/baldrick/pull/44
* add tests for the artifact poster by @Cadair in https://github.com/OpenAstronomy/baldrick/pull/48
* Add new method to access check run API by @pllim in https://github.com/OpenAstronomy/baldrick/pull/45
* Add logging to circleci handler by @Cadair in https://github.com/OpenAstronomy/baldrick/pull/50
* Remove support for post_pr_comment by @astrofrog in https://github.com/OpenAstronomy/baldrick/pull/49
* Ignore more files by @pllim in https://github.com/OpenAstronomy/baldrick/pull/52
* Add support for a fallback config by @Cadair in https://github.com/OpenAstronomy/baldrick/pull/51
* TST: Strict settings for pytest by @pllim in https://github.com/OpenAstronomy/baldrick/pull/62
* Expose handler classes in top level import by @pllim in https://github.com/OpenAstronomy/baldrick/pull/58
* Nothing to see here by @pllim in https://github.com/OpenAstronomy/baldrick/pull/54
* Added new plugin for defining custom actions on pushes to a repository by @astrofrog in https://github.com/OpenAstronomy/baldrick/pull/53
* Improve logic for closing stale issues by @astrofrog in https://github.com/OpenAstronomy/baldrick/pull/69
* Revive special message comment by @pllim in https://github.com/OpenAstronomy/baldrick/pull/67
* Special fix by @pllim in https://github.com/OpenAstronomy/baldrick/pull/70
* Special day prep for 2020 by @pllim in https://github.com/OpenAstronomy/baldrick/pull/72
* Fix stale PR script by @astrofrog in https://github.com/OpenAstronomy/baldrick/pull/74
* Fix name, update copyright year by @pllim in https://github.com/OpenAstronomy/baldrick/pull/75
* Allow specifying a single or list of actions to trigger pull_request_handler on by @adrn in https://github.com/OpenAstronomy/baldrick/pull/77
* Fix pull_request_handler decorator so that it works properly by @astrofrog in https://github.com/OpenAstronomy/baldrick/pull/80
* TST: Remove extraneous return by @pllim in https://github.com/OpenAstronomy/baldrick/pull/84
* ENH: Use check for PR instead of status by @pllim in https://github.com/OpenAstronomy/baldrick/pull/73
* Add a logger and update the config handling by @Cadair in https://github.com/OpenAstronomy/baldrick/pull/85
* Improvements to Checks by @Cadair in https://github.com/OpenAstronomy/baldrick/pull/87
* Implement allowing circleci plugin to report on not success by @Cadair in https://github.com/OpenAstronomy/baldrick/pull/96
* MNT: Do not use deprecated API, fix CI by @pllim in https://github.com/OpenAstronomy/baldrick/pull/98
* Add draft property for PR handler by @pllim in https://github.com/OpenAstronomy/baldrick/pull/99
* ENH: Add base branch checker for new PR by @pllim in https://github.com/OpenAstronomy/baldrick/pull/92
* Fix a substring bug in towncrier checker by @Cadair in https://github.com/OpenAstronomy/baldrick/pull/102
* retemplate and add azure by @Cadair in https://github.com/OpenAstronomy/baldrick/pull/101
* BUG: Fix config loads to avoid KeyError by @pllim in https://github.com/OpenAstronomy/baldrick/pull/104
* Rephrase missing milestone by @bsipocz in https://github.com/OpenAstronomy/baldrick/pull/106
* Nothing to see here by @pllim in https://github.com/OpenAstronomy/baldrick/pull/107
* MNT: Remove Travis CI by @pllim in https://github.com/OpenAstronomy/baldrick/pull/108
* [astropy-bot] BUG: A JSON web token could not be decoded by @pllim in https://github.com/OpenAstronomy/baldrick/pull/109
* Remove branch reference for `OpenAstronomy/azure-pipeline-templates` by @ConorMacBride in https://github.com/OpenAstronomy/baldrick/pull/115
* Use github default branch not master by @Cadair in https://github.com/OpenAstronomy/baldrick/pull/116
* Fix towncrier bug and pin version by @Cadair in https://github.com/OpenAstronomy/baldrick/pull/117
* New circleci webhooks by @Cadair in https://github.com/OpenAstronomy/baldrick/pull/119
* A bunch of infra updates by @Cadair in https://github.com/OpenAstronomy/baldrick/pull/120

### New Contributors
* @pllim made their first contribution in https://github.com/OpenAstronomy/baldrick/pull/44
* @adrn made their first contribution in https://github.com/OpenAstronomy/baldrick/pull/77
* @bsipocz made their first contribution in https://github.com/OpenAstronomy/baldrick/pull/106
* @ConorMacBride made their first contribution in https://github.com/OpenAstronomy/baldrick/pull/115

**Full Changelog**: https://github.com/OpenAstronomy/baldrick/compare/v0.2...v0.3

## 0.2 - 2018-11-22

- Make sure that when switching from single- to multi-status, we set any
  previous single checks to success, and edit previous comments. [#37]
- Fix an issue with RepoHandler.get_file_contents when the branch was not
  set to 'master'. [#37]
- Always post new status results, don't try and skip based on existing
  statuses. [#37]

## 0.1 - 2018-11-22

- Initial version
