import requests
from loguru import logger

from baldrick.blueprints.circleci import circleci_webhook_handler


@circleci_webhook_handler
def set_commit_status_for_artifacts(repo_handler, webhook_version, payload, headers, status, revision, build_number):
    commit_name = f"{repo_handler.repo}@{revision[:5]}"
    if webhook_version == "v2" and payload.get("type") != "job-completed":
        logger.trace("Ignoring not v2 'job-completed' webhook.")
        return None

    ci_config = repo_handler.get_config_value("circleci_artifacts", {})
    if not ci_config.get("enabled", False):
        msg = f"{commit_name} - Skipping circleci artifact check, disabled in config, but webhook configured."
        logger.info(msg)
        return msg

    repo = repo_handler.repo
    logger.info(f"{commit_name} - Processing CircleCI payload")
    artifacts = get_artifacts_from_build(repo, build_number, commit_name)

    # Remove enabled from the config list
    ci_config.pop("enabled", None)

    for name, config in ci_config.items():
        logger.trace(f"{commit_name} - Job {name=} {config=}")
        if not config.get("enabled", True) or (status != "success" and not config.get("report_on_fail", False)):
            continue

        if "url" not in config or "message" not in config:
            logger.warning(f"{commit_name} - Incorrectly configured job {name}, skipping because missing url or message")
            continue

        url = get_documentation_url_from_artifacts(artifacts, config["url"])

        if url:
            logger.debug(f"{commit_name} - Found artifact: {url}")
            repo_handler.set_status("success", config["message"], name, revision, url)

    return "All good"


def get_artifacts_from_build(repo, build_num, commit_name):  # pragma: no cover
    base_url = "https://circleci.com/api/v1.1"
    query_url = f"{base_url}/project/github/{repo}/{build_num}/artifacts"
    logger.debug(f"{commit_name} - Getting build {query_url}")
    response = requests.get(query_url)
    response.raise_for_status()
    return response.json()


def get_documentation_url_from_artifacts(artifacts, url):
    for artifact in artifacts:
        if url in artifact["path"]:
            return artifact["url"]
    return None
