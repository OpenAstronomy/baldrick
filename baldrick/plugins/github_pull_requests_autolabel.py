from os import path, sep

from baldrick.github.github_api import RepoHandler
from baldrick.plugins.github_pull_requests import pull_request_handler


def get_subpackage_labels(files, all_labels):
    """Loop through all modified file paths and extract the path elements for
    each of the files. Then see if any of these paths or subsets of the path
    exist as labels in the repo. This ignores the root of the path, so that,
    e.g., astropy/coordinates and docs/coordinates both get caught and matched
    to a "coordinates" label. Because this also considers all cumulative subsets
    of the path, the following all map to, e.g., a "coordinates" label:

        astropy/coordinates/file.py
        astropy/coordinates/tests/file.py
        astropy/coordinates/stuff/tests/file.py
        docs/coordinates/stuff/file.rst

    Parameters
    ----------
    files : iterable
        A list or iterable of full path names to files modified by a pull
        request.
    all_labels : iterable
        A list or iterable of all labels defined for the repository.

    Returns
    -------
    labels : set
        A set containing all subpackage labels to be added to the pull request
        that already exist in the input ``all_labels``.

    """
    labels = set()

    for file_ in files:
        # Each file_ is assumed to be a full path to a modified file within
        # the repository. This then grabs the directory name of the file_,
        # stripping off the filename itself:
        subdir = path.dirname(file_)

        # If we are in a subdirectory:
        if subdir:
            # Get the subdirectory root name (e.g., "packagename" or "docs"),
            # and the rest of the path:
            root, *subpkg = subdir.split(sep)

            if subpkg:
                # Consider all possible, cumulative path subsets:
                for i in range(len(subpkg)):
                    # Assume that the subpackage labels for sub-sub packages
                    # contain dots
                    dot_name = '.'.join(subpkg[:i + 1])

                    # Only add the label if it exists in the full list of
                    # repository labels
                    if dot_name in all_labels:
                        labels.add(dot_name)

    return labels


@pull_request_handler(actions=['opened'])
def autolabel(pr_handler, repo_handler):

    print(f'Running auto-labeller for {pr_handler.repo}#{pr_handler.number}')

    # Note: repo_handler is the fork, we need to use the upstream repository
    # for some tasks below.
    upstream_repo = RepoHandler(pr_handler.repo,
                                installation=pr_handler.installation)

    al_config = pr_handler.get_config_value("autolabel", {})
    if not al_config.get('enabled', False):
        return

    files = pr_handler.get_modified_files()

    print('  Modified files:')
    for file in files:
        print(f'    - {file}')

    all_labels = upstream_repo.get_all_labels()

    print('  All labels: ' + ', '.join(all_labels))

    pr_labels = set(pr_handler.labels)

    print('  Pull request labels: ' + ', '.join(pr_labels))

    new_labels = set()

    if al_config.get('subpackages', True):
        labels = get_subpackage_labels(files, all_labels)
        new_labels = new_labels.union(labels)

    if new_labels:
        final_labels = list(pr_labels.union(new_labels))
        print('  Final labels to set: ' + ', '.join(final_labels))
        pr_handler.set_labels(final_labels)

    return None
