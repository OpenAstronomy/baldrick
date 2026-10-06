Making a new baldrick release
=============================

A new release of baldrick is almost fully automated. As a maintainer it should
be nice and simple to do, especially if all merged pull requests have nice
titles and are correctly labelled.

Here is the process to follow to make a new release:

* Go through all the pull requests since the last release and make sure they
  have descriptive titles (these will become the changelog entries) and are
  labelled correctly (`enhancement`, `bug` or `documentation`; anything else
  ends up under "Other Changes").
* Go to the GitHub releases interface and draft a new release, creating a new
  tag of the form `vX.Y` (or `vX.Y.Z` for bug-fix releases).
* Use the GitHub "Generate release notes" button, which uses the configuration
  in `.github/release.yml` to group the entries under headings based on labels.
* Edit the draft release notes as required, in particular to call out major
  changes at the top.
* Publish the release. This triggers two workflows: the CI workflow builds the
  package and uploads it to PyPI, and the "Update Changelog" workflow adds the
  release notes to `CHANGES.md` on `main`.
