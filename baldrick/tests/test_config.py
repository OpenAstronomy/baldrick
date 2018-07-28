import pytest
from baldrick.config import Config, load, loads

GLOBAL_TOML = """
[tool.baldrick]

[tool.baldrick.plugin1]
setting1 = 'a'
setting2 = 'b'

[tool.baldrick.plugin2]
setting3 = 1
"""

REPO_TOML = """
[tool.testbot]

[tool.testbot.plugin1]
setting2 = 'c'

[tool.testbot.plugin2]
setting3 = 4
setting4 = 1.5

[tool.testbot.plugin3]
setting5 = 't'
"""


def test_loads():
    config = loads(GLOBAL_TOML)
    assert config.sections == {'plugin1': {'setting1': 'a', 'setting2': 'b'},
                               'plugin2': {'setting3': 1}}


def test_load(tmpdir):
    filename = tmpdir.join('pyproject.toml').strpath
    with open(filename, 'w') as f:
        f.write(GLOBAL_TOML)
    assert load(filename) == loads(GLOBAL_TOML)


def test_loads_invalid_tool():
    with pytest.raises(KeyError):
        loads(GLOBAL_TOML, tool='testbot')


def test_update_override():
    config_global = loads(GLOBAL_TOML)
    config_repo = loads(REPO_TOML, tool='testbot')
    config_global.update(config_repo)
    assert config_global.sections == {'plugin1': {'setting1': 'a', 'setting2': 'c'},
                                      'plugin2': {'setting3': 4, 'setting4': 1.5},
                                      'plugin3': {'setting5': 't'}}
