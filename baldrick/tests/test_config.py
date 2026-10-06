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
    assert config == {"plugin1": {"setting1": "a", "setting2": "b"}, "plugin2": {"setting3": 1}}


def test_load(tmpdir):
    filename = tmpdir.join("pyproject.toml").strpath
    with open(filename, "w") as f:
        f.write(GLOBAL_TOML)
    assert load(filename) == loads(GLOBAL_TOML)


def test_loads_invalid_tool():
    conf = loads(GLOBAL_TOML, tool="testbot")
    assert conf is None


def test_update_override():
    config_global = loads(GLOBAL_TOML)
    config_repo = loads(REPO_TOML, tool="testbot")
    config_global.update_from_config(config_repo)
    assert config_global == {
        "plugin1": {"setting1": "a", "setting2": "c"},
        "plugin2": {"setting3": 4, "setting4": 1.5},
        "plugin3": {"setting5": "t"},
    }


def test_copy():
    conf = Config({"a": 1})
    conf_copy = conf.copy()
    assert isinstance(conf_copy, Config)
    assert conf_copy == {"a": 1}


def test_copy_does_not_share_sections():
    conf = Config({"plugin1": {"setting1": "a"}})
    conf_copy = conf.copy()
    conf_copy.update_from_config(Config({"plugin1": {"setting1": "b"}}))
    assert conf["plugin1"]["setting1"] == "a"
    assert conf_copy["plugin1"]["setting1"] == "b"


def test_summary_truncates_long_strings():
    conf = Config({"plugin1": {"short": "abc", "number": 3, "long": "x" * 100}})
    assert conf.summary(max_length=10) == repr(
        {"plugin1": {"short": "abc", "number": 3, "long": "xxxxxxxxxx... [100 characters]"}}
    )
