.. image:: https://dev.azure.com/OpenAstronomy/baldrick/_apis/build/status/OpenAstronomy.baldrick?branchName=master
    :target: https://dev.azure.com/OpenAstronomy/baldrick/_build/latest?definitionId=1&branchName=master

.. image:: https://codecov.io/gh/OpenAstronomy/baldrick/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/OpenAstronomy/baldrick


Baldrick: A cunning plan for GitHub bots
----------------------------------------

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


Licence
-------

This project is licensed under the MIT licence.
