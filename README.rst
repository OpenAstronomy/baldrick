.. image:: https://travis-ci.org/OpenAstronomy/baldrick.svg
    :target: https://travis-ci.org/OpenAstronomy/baldrick

.. image:: https://codecov.io/gh/OpenAstronomy/baldrick/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/OpenAstronomy/baldrick


Baldrick: The Bot with a Cunning Plan
-------------------------------------

This is a (GitHub) bot framework which is designed to have a pluggable and
configurable setup for responding to webhooks.

Baldrick grew out of `astropy-bot <https://github.com/astropy/astropy-bot>`__
but refactored to be generic and easy to configure.


Usage
-----

Baldrick is designed to be imported and used to construct a Flask app. An
example repository which could be deployed on
`Dokku <http://dokku.viewdocs.io/>`__ or `Heroku <https://www.heroku.com/>`__
can be found in the `example/` directory.


Licence
-------

This project is licensed under the MIT licence.
