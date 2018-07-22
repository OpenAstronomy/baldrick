from setuptools import setup, find_packages

setup(version='0.0.dev0',
      name="baldrick",
      description="Helpers for GitHub bots",
      url='https://github.com/astrofrog/baldrick',
      packages=find_packages(),
      author='Stuart Mumford and Thomas Robitaille',
      install_requires=[
          "flask",
          "flask-dance",
          "pyjwt",
          "requests",
          "cryptography",
          "python-dateutil",
          "humanize",
          "toml"])
