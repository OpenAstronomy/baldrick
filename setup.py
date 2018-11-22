from setuptools import setup, find_packages

entry_points = {}
entry_points['console_scripts'] = ['check-stale-issues = baldrick.scripts.stale_issues:main',
                                   'check-stale-pull-requests = baldrick.scripts.stale_pull_requests:main']

with open('README.rst') as f:
    long_description = f.read()

setup(version='0.1',
      name="baldrick",
      description="baldrick: a cunning plan for GitHub bots",
      long_description=long_description,
      url='https://github.com/astrofrog/baldrick',
      packages=find_packages(),
      author='Stuart Mumford and Thomas Robitaille',
      author_email='thomas.robitaille@gmail.com',
      entry_points=entry_points,
      extras_require={'test': ['pytest>=3.5,<3.7', 'pytest-flake8', 'pytest-cov', 'codecov', 'towncrier'],
                      'docs': ['sphinx', 'sphinx-automodapi']},
      install_requires=[
          "flask",
          "pyjwt",
          "requests",
          "python-dateutil",
          "cryptography",
          "humanize",
          "towncrier",
          "toml",
          "ttldict"])
