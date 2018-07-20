import requests

from .circleci import circleci_webhook_handler


HOST = "https://api.github.com"


@circleci_webhook_handler
def set_commit_status_for_artifacts(repo_handler, payload, headers):
    if payload['status'] == 'success':
        artifacts = get_artifacts_from_build(payload)

        urls = repo_handler.get_config_value("circleci_artifacts",
                                             {"sphinx": {
                                                 "url": "html/index.html",
                                                 "message":
                                                 "Click details to preview the documentation build"}})

        for name, config in urls.items():

            url = get_documentation_url_from_artifacts(artifacts, config['url'])

            if url:
                repo_handler.set_status(payload['vcs_revision'],
                                        name,
                                        "success",
                                        config['message'],
                                        url)

    return "All good"


def get_artifacts_from_build(p):
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
