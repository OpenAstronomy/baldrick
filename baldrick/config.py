import tomllib


def load(file, tool="baldrick"):
    with open(file, "rb") as f:
        conf = tomllib.load(f)
    if "tool" in conf and tool in conf["tool"]:
        return Config(conf["tool"][tool])
    return None


def loads(text, tool="baldrick"):
    conf = tomllib.loads(text)
    if "tool" in conf and tool in conf["tool"]:
        return Config(conf["tool"][tool])
    return None


class Config(dict):
    def update_from_config(self, other_config):
        for section_name, section in other_config.items():
            if section_name not in self:
                self[section_name] = {}
            for setting, value in section.items():
                self[section_name][setting] = value

    def copy(self):
        # Copy the sections too, so that updating the copy does not modify the
        # sections of the original configuration.
        return Config(
            {
                section_name: dict(section) if isinstance(section, dict) else section
                for section_name, section in self.items()
            }
        )

    def summary(self, max_length=60):
        """
        A representation of the configuration with long string values
        truncated, for logging.
        """
        summary = {}
        for section_name, section in self.items():
            if not isinstance(section, dict):
                summary[section_name] = section
                continue
            summary[section_name] = {}
            for setting, value in section.items():
                if isinstance(value, str) and len(value) > max_length:
                    value = value[:max_length] + f"... [{len(value)} characters]"
                summary[section_name][setting] = value
        return repr(summary)
