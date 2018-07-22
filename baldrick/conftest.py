import os

from baldrick import create_app

app = None


def pytest_configure():
    os.environ['GITHUB_APP_INTEGRATION_ID'] = '1234'
    os.environ['GITHUB_APP_PRIVATE_KEY'] = 'ABCD'
    global app
    app = create_app('testbot')


def pytest_unconfigure(config):
    global app
    app = None
