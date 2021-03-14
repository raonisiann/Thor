import json
import os
from thor.lib.base import Base


class ConfigException(Exception):
    pass


class Config(Base):

    def __init__(self, config_path):
        super().__init__()
        self.config_path = config_path
        self.loaded_config = {}

    def load_config_file(self):
        if os.path.exists(self.config_path):
            self.logger.info('Loading config file %s', self.config_path)
            with open(self.config_path) as f:
                return json.loads(f.read())
        # no config file available
        return None

    def lazy_load_config(self):
        if self.loaded_config:
            return
        json_config = self.load_config_file()
        if json_config:
            self.__load_config_dict_rec(json_config, '')

    def __load_config_dict_rec(self, node, base):
        for name, value in node.items():
            config_path = '{base}.{name}' if base else '{base}{name}'
            config_path = config_path.format(
                base=base,
                name=name
            )
            if type(value) is dict:
                self.__load_config_dict_rec(value, config_path)
            else:
                self.loaded_config[config_path] = value

    def get_by_prefix(self, name):
        self.lazy_load_config()
        matches = {}
        for k, v in self.loaded_config.items():
            if k.startswith(name):
                matches[k[len(name)+1:]] = v
        return matches

    def get(self, name):
        self.lazy_load_config()
        if name in self.loaded_config:
            return self.loaded_config[name]
        else:
            return None

    def set(self, name, value):
        self.lazy_load_config()
        if name is not str:
            raise ConfigException('Config name must be an string')
        self.loaded_config[name] = value