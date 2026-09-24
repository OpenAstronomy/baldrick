import hashlib
import hmac
import json
import logging
import os

import pytest
from loguru import logger
from unittest.mock import patch, MagicMock

from baldrick.github.github_auth import GithubAppAuth

PRIVATE_KEY = """
-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEA8QIt+M5C6ayAzQVSS4CfXr4VXJ47veAazH+YQ6ZfO6OQ/p3T
+8jrW43SLXS/DmOJzEMKAox9ar/4E2N4wh8uGI3qd2q68wkJk0EPRkFHqnFs5o8c
PjxOeVG2KlbtJu0VRoQ+uZSl2B+AZeQZdK9aWPXjCTZbPoIeMERJqZtZfmwZIosx
ExRtRPIftSpDzEdZZtvq8+DC+w5hudrlpQFqsUwUv/BjcQINAp+i5B8GuDzjYaJ0
2cm/j7moMYBaoBr0QCpAqBseE6mjXXbBmIlO70Wy2OGbqnBblrowIFAxh/28h/P9
4V0AVJrBT8gFoa1ODqLcL8C+ob0TRRuncU2q2QIDAQABAoIBADc+FqeHL9M8FTHp
XFmuG9mtnFvkcTEuozXosVAgXIfhECUsrCB0h24u7dQ5hGmZ60YEv9Chv0WuxwA6
tr1YREqgjPPeZQe8NJOqQAQMho7M/PdEKmchj6NDVYwS7L0VbuEBAxequPD3F4lD
ZYpXf1AQ3H+KFBQZ4y2RGYlk8HiHgMQ0h+faX6xO8cWtVgSb6C7/ibQPPTxMCB59
Fq2iJizJdY3kiWUmKpnl3yHoUasUi5WkgJqFg4RkVVN6MnCavhny6xvNgaSdKs+H
0NTus7lanC80xqXtXgsu53Oq1fN+4I2qX+e6Kv1CHPPCWcTgNy7/zw+vWhUlyKR0
tP8KSXkCgYEA+Txxheoi3OxDx1R/iD3SePFeIg0rW/zBFseVW6AFz/IUQwh4kQl/
pShVb/qRcj0YOmflIC/8S5vlJk9iC1ExFpypJXf3N33k2k1oyN6U40Mn73PkfCXn
59o2ecr2pgSauaO/x8XoP2M8dJS8VHOSaJaJ0lu8aQ6jvICUmVtDzSsCgYEA94yT
Rqz6TBmVDdOlLqgoG4tGfVhlAwAwYgvHjBYUHRmLjmEH+PU8RDNOtuMEtWG2oLCp
1LJsc3oWQkl3nAzfuyJyiNsgOqql4bFttJ14Esgx+4hrSHCYEBE6w1fvansXJBRQ
VmHntGA5Akt3+6GdILgoVz12uNEZTvVhTM3CjgsCgYBJOfgEp1jc3dHAI9RgfAF1
pTzJ9mKR4T396l+4jtiGUxKe60M5IbhOFv6bKtxG2ypeJp5MCa0vrbryuYoN1yn8
AcU0i/2nYSa2+N1bfwHxj46RLNSpoR10okk1GWvENUAcYL78++mTjh16ByUaDuaq
MeiGVIuTtkhnHsQKFqViBwKBgEgR3S7OXXCaYhLMc2LKAiNCwRrtCTt+apeg5k+a
ffCa505kYXXRr+ILLfeA0HYeJJVT2Z3a9EgKW0ChMvlzpg9NUBsX8KIj3HeAuHfF
AJg3QJYCeXl1jk/fNER67XEKtQoD//+mMVcKTI6meiAARUapVtVPR6k29y9NsS4z
GVlRAoGAV9jg9e94lqMNZqY2CY6LISnUPGOMSN0Z5xC+Q7C6lqWZOGRcxRv2WdO3
ZYQCTqpbe2XTdqx7a3jh5zq2hOlPv97Q9v09Jdmkcak8vb/5DfXo61fOGF+PCSHQ
IJVMoU0lvK0zKm5VlXh3jbRXt/M5cTNu/1+xZxUbGJ0b+Go3FYc=
-----END RSA PRIVATE KEY-----
""".strip()

WEBHOOK_SECRET = "baldrick-test-webhook-secret"

INTEGRATION_ID = 1234

TOKEN_RESPONSE_VALID = {"token": "v1.1f699f1069f60xxx", "expires_at": "2016-07-11T22:14:10Z"}


def auth_requests_patch(url, headers=None):
    """
    Mock ``requests.get`` for the URLs used while constructing and using a
    ``GithubAppAuth`` instance.
    """
    req = MagicMock()
    req.status_code = 200
    req.ok = True
    if url == "https://api.github.com/app":
        req.json.return_value = {"name": "testbot", "installations_count": 2}
    elif url == "https://api.github.com/app/installations":
        req.json.return_value = [{"id": 3331}]
    elif url == "https://api.github.com/installation/repositories":
        req.json.return_value = {
            "repositories": [{"full_name": "test1"}, {"full_name": "test2"}, {"full_name": "test/testbot"}]
        }
    return req


@pytest.fixture
def create_app_mocks(mocker):
    mocker.patch("requests.get", auth_requests_patch)
    post = mocker.patch("requests.post")
    post.return_value.ok = True
    post.return_value.json.return_value = TOKEN_RESPONSE_VALID


@pytest.fixture
def auth(create_app_mocks):
    """
    A ``GithubAppAuth`` instance with all GitHub API interactions mocked out.
    """
    return GithubAppAuth(INTEGRATION_ID, PRIVATE_KEY)


@pytest.fixture
def app(create_app_mocks):
    from baldrick import create_app

    os.environ["GITHUB_APP_INTEGRATION_ID"] = "1234"
    os.environ["GITHUB_APP_PRIVATE_KEY"] = PRIVATE_KEY
    os.environ["GITHUB_APP_WEBHOOK_SECRET"] = WEBHOOK_SECRET

    return create_app("testbot")


@pytest.fixture
def github_webhook_headers():
    """
    Build request headers containing a valid ``X-Hub-Signature-256``
    signature for the given payload, matching the secret set by the ``app``
    fixture.
    """

    def make_headers(payload, headers=None):
        if isinstance(payload, str):
            body = payload.encode("utf-8")
        elif isinstance(payload, (bytes, bytearray)):
            body = bytes(payload)
        else:
            body = json.dumps(payload).encode("utf-8")
        signature = "sha256=" + hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
        all_headers = {"X-Hub-Signature-256": signature}
        if headers:
            all_headers.update(headers)
        return all_headers

    return make_headers


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def caplog(caplog):
    """
    Override the default pytest caplog fixture to work with loguru.
    """

    # Remove all logging but this redirect to standard logging
    logger.remove()

    class PropogateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropogateHandler(), format="{message}")

    yield caplog

    logger.remove(handler_id)
