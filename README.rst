Baldrick: A cunning plan for GitHub bots
----------------------------------------

.. image:: https://github.com/OpenAstronomy/baldrick/actions/workflows/ci.yml/badge.svg?branch=main
    :target: https://github.com/OpenAstronomy/baldrick/actions/workflows/ci.yml?query=branch%3Amain

.. image:: https://img.shields.io/pypi/v/baldrick.svg
   :target: https://pypi.python.org/pypi/baldrick/


This is a (GitHub) bot framework which is designed to have a pluggable and
configurable setup for responding to webhooks.

Baldrick grew out of `astropy-bot <https://github.com/astropy/astropy-bot>`__
but refactored to be generic and easy to configure.


Usage
-----

Baldrick is designed to be imported and used to construct a Flask app. An
example repository which could be deployed on
`Dokku <http://dokku.viewdocs.io/>`__ or `Heroku <https://www.heroku.com/>`__
can be found in the ``template`` directory.

Cadair hosts an instance called `Giles <https://github.com/cadair/giles>`__.


Licence
-------

This project is licensed under the MIT licence.
