import json
import os
from thor.lib.base import Base


class ConfigUnknownKeyException(Exception):
    pass


class ConfigException(Exception):
    pass


class Config(Base):

    def __init__(self, config_path):
        super().__init__()
        self.config_path = config_path
        self.loaded_config = None

    def lazy_load_config(self):
        if self.loaded_config is None:
            if os.path.exists(self.config_path):
                self.logger.info('Loading config file %s', self.config_path)
                with open(self.config_path) as f:
                    return json.loads(f.read())
            else:
                self.loaded_config = {}

    def __set_config_recursive(self, path, value, config):
        path_splited = path.split('.')
        left = path_splited[0]
        new = config

        if type(config) is list and left.isnumeric():
            left = int(left)
            try:
                config[left]
            except KeyError:
                config[left] = []

        if type(config) is dict and left not in config:
            new[left] = {}
        # recurse to sub nodes...
        if len(path_splited) > 1:
            new[left] = self.__set_config_recursive(
                '.'.join(path_splited[1:]), value, new[left])
        else:
            new[left] = value

        return new

    def __get_config_recursive(self, path):
        if path == '' or path == '.':
            return self.loaded_config

        path_splited = path.split('.')
        config_base = self.loaded_config

        for name in path_splited:
            try:
                if type(config_base) is list and name.isnumeric():
                    name = int(name)
                config_base = config_base[name]
            except (IndexError, KeyError):
                self.logger.error('Cannot access {}'.format(name))
                raise ConfigUnknownKeyException(name)
        return config_base

    def get(self, path=''):
        self.lazy_load_config()
        return self.__get_config_recursive(path)

    def set(self, path, value):
        self.lazy_load_config()

        if not path:
            raise ConfigException('Path cannot be empty')

        self.loaded_config = self.__set_config_recursive(
            path, value, self.loaded_config)
