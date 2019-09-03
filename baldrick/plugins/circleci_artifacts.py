import requests

from loguru import logger

from baldrick.blueprints.circleci import circleci_webhook_handler


@circleci_webhook_handler
def set_commit_status_for_artifacts(repo_handler, payload, headers):

    ci_config = repo_handler.get_config_value("circleci_artifacts", {})
    if not ci_config.get("enabled", False):
        msg = "Skipping artifact check, disabled in config."
        logger.debug(msg)
        return msg

    if payload['status'] == 'success':
        logger.info(f"Got CircleCI 'success' status for repo: {payload['username']}/{payload['reponame']}")
        artifacts = get_artifacts_from_build(payload)

        for name, config in ci_config.items():

            if name == 'enabled':
                continue

            url = get_documentation_url_from_artifacts(artifacts, config['url'])
            logger.debug(f"Found artifact: {url}")

            if url:
                repo_handler.set_status("success",
                                        config["message"],
                                        name,
                                        payload["vcs_revision"],
                                        url)

    return "All good"


def get_artifacts_from_build(p):  # pragma: no cover
    base_url = "https://circleci.com/api/v1.1"
    query_url = f"{base_url}/project/github/{p['username']}/{p['reponame']}/{p['build_num']}/artifacts"
    response = requests.get(query_url)
    assert response.ok, response.content
    return response.json()


def get_documentation_url_from_artifacts(artifacts, url):
    for artifact in artifacts:
        # Find the root sphinx index.html
        if url in artifact['path']:
            return artifact['url']
