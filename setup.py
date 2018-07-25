from setuptools import setup, find_packages

entry_points = {}
entry_points['console_scripts'] = ['check-stale-issues = baldrick.scripts.stale_issues:main',
                                   'check-stale-pull-requests = baldrick.scripts.stale_pull_requests:main']

setup(version='0.0.dev0',
      name="baldrick",
      description="Helpers for GitHub bots",
      url='https://github.com/astrofrog/baldrick',
      packages=find_packages(),
      author='Stuart Mumford and Thomas Robitaille',
      entry_points=entry_points,
      extras_require={'test': ['pytest>=3.5', 'pytest-flake8', 'pytest-cov', 'codecov']},
      install_requires=[
          "flask",
          "pyjwt",
          "requests",
          "python-dateutil",
          "humanize",
          "toml",
          "ttldict"])
