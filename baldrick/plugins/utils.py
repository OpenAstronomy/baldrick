from flask import current_app

__all__ = ["get_config_with_app_defaults"]


def get_config_with_app_defaults(repo_handler, config_section, default=None):
    """
    Read the config section and check if the app has a default for that section.

    Default values for the config section can be specified by adding an
    attribute to the app with the name ``config_section_default``. This will be
    used if the section is not specified in the ``pyproject.toml`` file. If
    neither are specified then the plugin should not run.
    """
    default_conf = getattr(current_app, config_section + "_default", default)
    return repo_handler.get_config_value(config_section, default_conf)
