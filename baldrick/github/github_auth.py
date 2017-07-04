import time
import dateutil.parser
import datetime

import jwt

import requests

TEN_MIN = datetime.timedelta(minutes=9)
ONE_MIN = datetime.timedelta(minutes=1)

# TODO: need to change global variable to use redis

json_web_token = None
json_web_token_expiry = None


def parse_iso_datetime(timestamp):
    return datetime.datetime(*time.strptime(timestamp, "%Y-%m-%dT%H:%M:%S")[:6])


def get_json_web_token():
    """
    Prepares the JSON Web Token (JWT) based on the private key.
    """

    global json_web_token
    global json_web_token_expiry

    from .webapp import app

    now = datetime.datetime.now()

    # Include a one-minute buffer otherwise token might expire by the time we
    # make the request with the token.
    if json_web_token_expiry is None or now + ONE_MIN > json_web_token_expiry:

        json_web_token_expiry = now + TEN_MIN

        payload = {}

        # Issued at time
        payload['iat'] = int(now.timestamp())

        # JWT expiration time (10 minute maximum)
        payload['exp'] = int(json_web_token_expiry.timestamp())

        # Integration's GitHub identifier
        payload['iss'] = app.integration_id

        json_web_token = jwt.encode(payload,
                                    app.private_key.encode('ascii'),
                                    algorithm='RS256').decode('ascii')

    return json_web_token


# TODO: update this to support multiple installation tokens
installation_token = None
installation_token_expiry = None


def get_installation_token(installation):
    """
    Get access token for installation
    """

    global installation_token
    global installation_token_expiry

    now = datetime.datetime.now().timestamp()

    if installation_token_expiry is None or now + 60 > installation_token_expiry:

        # FIXME: if .netrc file is present, Authorization header will get
        # overwritten, so need to figure out how to ignore that file.
        headers = {}
        headers['Authorization'] = 'Bearer {0}'.format(get_json_web_token())
        headers['Accept'] = 'application/vnd.github.machine-man-preview+json'

        url = 'https://api.github.com/installations/{0}/access_tokens'.format(installation)

        req = requests.post(url, headers=headers)

        resp = req.json()

        installation_token = resp['token']
        # FIXME: need to parse string
        installation_token_expiry = dateutil.parser.parse(resp['expires_at']).timestamp()

    return installation_token


def github_request_headers(installation):

    token = get_installation_token(installation)

    headers = {}
    headers['Authorization'] = 'token {0}'.format(token)
    headers['Accept'] = 'application/vnd.github.machine-man-preview+json'

    return headers
