import toml


def load(file, tool='baldrick'):
    conf = toml.load(file)
    if 'tool' in conf and tool in conf['tool']:
        return Config(conf['tool'][tool])


def loads(text, tool='baldrick'):
    return Config(toml.loads(text)['tool'][tool])


class Config(dict):

    def update_from_config(self, other_config):
        for section_name, section in other_config.items():
            if section_name not in self:
                self[section_name] = {}
            for setting, value in section.items():
                self[section_name][setting] = value

    def copy(self):
        return Config(super().copy())
