import os
import re
from collections import OrderedDict

import toml

from flask import current_app

from .pull_request_handler import pull_request_handler


try:
    from towncrier._settings import parse_toml
except ImportError:
    from towncrier._settings import _template_fname, _start_string, _title_format, _underlines, _default_types

    def parse_toml(config):
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


def load_towncrier_config(repo_handler):
    """
    Load the pyproject.yaml file from the repo.

    This adds a default `tool.towncrier` section.
    """
    try:
        pyproject = repo_handler.get_file_contents("pyproject.toml")
        pyproject = toml.loads(pyproject)
    except FileNotFoundError:
        pyproject = {'tool': {'towncrier': {}}}

    return parse_toml(pyproject)


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


def get_docs_url(pyproject):
    if 'tool' in pyproject:
        if current_app.bot_username in pyproject['tool']:
            return pyproject['tool'][current_app.bot_username]['towncrier_status_url']


def get_skill_config(pyproject):
    if 'tool' in pyproject:
        if current_app.bot_username in pyproject['tool']:
            return pyproject['tool'][current_app.bot_username]


def verify_pr_number(pr_number, matching_file):
    # TODO: Make this a regex to check that the number is in the right place etc.
    return pr_number in matching_file


NO_CHANGELOG = "No changelog file was added in the correct directories."

WRONG_TYPE = "The changelog file that was added is not one of the configured types."

WRONG_NUMBER = "The number in the changelog file does not match this pull request number."


@pull_request_handler
def process_towncrier_changelog(pr_handler, repo_handler, headers):

    cl_config = repo_handler.get_config_value('towncrier_changelog', {})

    if not cl_config:
        return [], None

    skip_label = cl_config.get('changelog_skip_label', None)

    config = load_towncrier_config(repo_handler)
    section_dirs = calculate_fragment_paths(config)
    types = config['types'].keys()

    modified_files = pr_handler.get_modified_filenames()

    messages = []
    matching_file = check_sections(modified_files, section_dirs)
    if not matching_file:
        messages.append(cl_config.get("missing_file_message", NO_CHANGELOG))

    else:
        if not check_changelog_type(types, matching_file):
            messages.append(cl_config.get("wrong_type_message", WRONG_TYPE))
        if cl_config.get('verify_pr_number', False) and not verify_pr_number(pr_handler.number, matching_file):
            messages.append(cl_config.get("wrong_number_message", WRONG_NUMBER))

    if skip_label and skip_label in pr_handler.labels:
        messages = []

    if not repo_handler.get_config_value('post_pr_comment', False):
        if messages:
            message = ' '.join(messages)
            pr_handler.set_status('failure', message, current_app.bot_username + ': changelog',
                                  target_url=cl_config.get('help_url', None))
            return [], None
        else:
            pr_handler.set_status('success', "The changelog looks good.", current_app.bot_username + ': changelog')
            return [], None
    else:
        if messages:
            return messages, False
        else:
            return [], True
