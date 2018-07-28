import toml


def load(file, tool='baldrick'):
    return Config(toml.load(file)['tool'][tool])


def loads(text, tool='baldrick'):
    return Config(toml.loads(text)['tool'][tool])


class Config:

    def __init__(self, sections=None):
        self.sections = sections or {}

    def update(self, other_config):
        for section_name, section in other_config.sections.items():
            if section_name not in self.sections:
                self.sections[section_name] = {}
            for setting, value in section.items():
                self.sections[section_name][setting] = value

    def __eq__(self, other):
        return self.sections == other.sections

    def copy(self):
        return Config(self.sections.copy())
