import os
import re
from collections import OrderedDict

from loguru import logger
from toml import loads

from .github_pull_requests import pull_request_handler

try:
    from towncrier._settings import parse_toml
except ImportError:  # pragma: nocover
    from towncrier._settings import _template_fname, _start_string, _title_format, _underlines, _default_types

    def parse_toml(config):  # pragma: nocover
        if 'tool' not in config:
            raise ValueError("No [tool.towncrier] section.")

        config = config['tool']['towncrier']

        sections = OrderedDict()
        types = OrderedDict()

        if "section" in config:
            for x in config["section"]:
                sections[x.get('name', '')] = x['path']
        else:
            sections[''] = ''

        if "type" in config:
            for x in config["type"]:
                types[x["directory"]] = {"name": x["name"],
                                         "showcontent": x["showcontent"]}
        else:
            types = _default_types

        return {
            'package': config.get('package', ''),
            'package_dir': config.get('package_dir', '.'),
            'filename': config.get('filename', 'NEWS.rst'),
            'directory': config.get('directory'),
            'sections': sections,
            'types': types,
            'template': config.get('template', _template_fname),
            'start_line': config.get('start_string', _start_string),
            'title_format': config.get('title_format', _title_format),
            'issue_format': config.get('issue_format'),
            'underlines': config.get('underlines', _underlines)
        }


def calculate_fragment_paths(config):

    if config.get("directory"):
        base_directory = config["directory"]
        fragment_directory = None
    else:
        base_directory = os.path.join(config['package_dir'], config['package'])
        fragment_directory = "newsfragments"

    section_dirs = []
    for key, val in config['sections'].items():
        if fragment_directory is not None:
            section_dirs.append(os.path.join(base_directory, val, fragment_directory))
        else:
            section_dirs.append(os.path.join(base_directory, val))

    return section_dirs


def check_sections(filenames, sections):
    """
    Check that a file matches ``<section><issue number>``. Otherwise the root
    dir matches when it shouldn't.
    """
    for section in sections:
        # Make sure the path ends with a /
        if not section.endswith("/"):
            section += "/"
        pattern = section.replace("/", r"\/") + r"\d+.*"
        for fname in filenames:
            match = re.match(pattern, fname)
            if match is not None:
                return fname
    return False


def check_changelog_type(types, matching_file):
    for ty in types:
        if ty in matching_file:
            return True
    return False


def verify_pr_number(pr_number, matching_file):
    # TODO: Make this a regex to check that the number is in the right place etc.
    return pr_number in matching_file


def load_towncrier_config(pr_handler):
    file_content = pr_handler.get_file_contents("pyproject.toml", branch=pr_handler.base_branch)
    config = loads(file_content)
    if "towncrier" in config.get("tool", {}):
        return parse_toml(config)


CHANGELOG_EXISTS = "Changelog file was added in the correct directories."
CHANGELOG_MISSING = "No changelog file was added in the correct directories."

TYPE_CORRECT = "The changelog file that was added is one of the configured types."
TYPE_INCORRECT = "The changelog file that was added is not one of the configured types."

NUMBER_CORRECT = "The number in the changelog file matches this pull request number."
NUMBER_INCORRECT = "The number in the changelog file does not match this pull request number."


@pull_request_handler
def process_towncrier_changelog(pr_handler, repo_handler):

    cl_config = pr_handler.get_config_value('towncrier_changelog', {})

    if not cl_config.get('enabled', False):
        logger.debug("Skipping towncrier changelog plugin as disabled in config")
        return None

    logger.debug(f"Checking towncrier changelog on {pr_handler.repo}#{pr_handler.number}")
    skip_label = cl_config.get('changelog_skip_label', None)

    config = load_towncrier_config(pr_handler)
    if not config:
        logger.info(f"No towncrier config detected in pyproject.toml, skipping.")
        return

    section_dirs = calculate_fragment_paths(config)
    types = config['types'].keys()

    modified_files = pr_handler.get_modified_files()

    matching_file = check_sections(modified_files, section_dirs)

    messages = {}

    if skip_label and skip_label in pr_handler.labels:
        # Returning nothing marks all existing checks as neutral
        return

    elif not matching_file:

        messages['missing_file'] = {
            'name': cl_config.get('changelog_missing_name', "changelog: Missing"),
            'title': cl_config.get('changelog_missing', CHANGELOG_MISSING),
            'summary': cl_config.get('changelog_missing_long', ''),
            'conclusion': 'failure'
        }

    else:
        report_success = True
        if check_changelog_type(types, matching_file):
            messages['wrong_type'] = {'name': cl_config.get('type_correct_name', 'changelog: Type correct'),
                                      'title': cl_config.get('type_correct', TYPE_CORRECT),
                                      'summary': cl_config.get('type_correct_long', ''),
                                      'conclusion': 'success',
                                      'skip_if_missing': True}
        else:
            report_success = False
            messages['wrong_type'] = {'name': cl_config.get('type_incorrect_name', 'changelog: Type incorrect'),
                                      'title': cl_config.get('type_incorrect', TYPE_INCORRECT),
                                      'summary': cl_config.get('type_incorrect_long', ''),
                                      'conclusion': 'failure'}

        if cl_config.get('verify_pr_number', False):
            if verify_pr_number(pr_handler.number, matching_file):
                report_success = False
                messages['wrong_number'] = {'name': cl_config.get('number_incorrect_name', 'changelog: Number not PR number'),
                                            'title': cl_config.get('number_incorrect', NUMBER_INCORRECT),
                                            'summary': cl_config.get('number_incorrect_long', ''),
                                            'conclusion': 'failure'}
            else:
                messages['wrong_number'] = {'name': cl_config.get('number_correct_name', 'changelog: Number correct'),
                                            'title': cl_config.get('number_correct', NUMBER_CORRECT),
                                            'summary': cl_config.get('number_correct_long', ''),
                                            'conclusion': 'success',
                                            'skip_if_missing': True}

        messages['missing_file'] = {
            'name': cl_config.get('changelog_exists_name', 'changelog: Found'),
            'title': cl_config.get('changelog_exists', CHANGELOG_EXISTS),
            'summary': cl_config.get('changelog_exists_long', ''),
            'conclusion': 'success'
        }

    # Add help URL
    for message in messages.values():
        message['details_url'] = cl_config.get('help_url', None)

    return messages
