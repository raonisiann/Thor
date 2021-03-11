import json
import os


class ConfigException(Exception):
    pass


class Config:

    LOADED_CONFIG = {}

    def __init__(self, config_path):
        self.__config_path = config_path
        self.load_config()

    def load_config_file(self):

        if os.path.exists(self.__config_path):
            with open(self.__config_path) as f:
                return json.loads(f.read())
        # no config file available
        return None

    def load_config(self):

        if Config.LOADED_CONFIG:
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
                Config.LOADED_CONFIG[config_path] = value

    def get(self, name):
        if name in Config.LOADED_CONFIG:
            return Config.LOADED_CONFIG[name]
        else:
            return None

    def set(self, name, value):
        if name is not str:
            raise ConfigException('Config name must be an string')
        Config.LOADED_CONFIG[name] = value