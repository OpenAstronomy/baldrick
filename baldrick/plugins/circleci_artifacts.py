import requests

from loguru import logger

from baldrick.blueprints.circleci import circleci_webhook_handler


@circleci_webhook_handler
def set_commit_status_for_artifacts(repo_handler, webhook_version, payload, headers, status, revision, build_number):
    if webhook_version == "v2" and payload.get("type") != "job-completed":
        msg = "Ignoring not 'job-completed' webhook."
        logger.debug(msg)
        return

    ci_config = repo_handler.get_config_value("circleci_artifacts", {})
    if not ci_config.get("enabled", False):
        msg = "Skipping artifact check, disabled in config."
        logger.debug(msg)
        return msg

    repo = repo_handler.repo
    logger.info(f"Got CircleCI payload for repo: {repo}")
    artifacts = get_artifacts_from_build(repo, build_number)

    # Remove enabled from the config list
    ci_config.pop("enabled", None)

    for name, config in ci_config.items():
        if not config.get("enabled", True) and (status != "success" and not config.get("report_on_fail", False)):
            continue

        url = get_documentation_url_from_artifacts(artifacts, config['url'])

        if url:
            logger.debug(f"Found artifact: {url}")
            repo_handler.set_status("success",
                                    config["message"],
                                    name,
                                    revision,
                                    url)

    return "All good"


def get_artifacts_from_build(repo, build_num):  # pragma: no cover
    base_url = "https://circleci.com/api/v1.1"
    query_url = f"{base_url}/project/github/{repo}/{build_num}/artifacts"
    logger.debug(f"Getting build {query_url}")
    response = requests.get(query_url)
    assert response.ok, response.content
    return response.json()


def get_documentation_url_from_artifacts(artifacts, url):
    for artifact in artifacts:
        if url in artifact['path']:
            return artifact['url']
