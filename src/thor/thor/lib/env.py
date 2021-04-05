import os

from thor.lib.aws import Aws
from thor.lib.base import Base
from thor.lib.config import (
    Config,
    ConfigUnknownKeyException
)
from thor.lib.thor import Thor


class EnvException(Exception):
    pass


class EnvAlreadyExistsException(Exception):
    pass


class EnvNotFoundException(Exception):
    pass


class EnvInvalidDirException(Exception):
    pass


class EnvCreationException(Exception):
    pass


class Env(Base):

    __AWS_CLIENT_CACHE = {}

    def __init__(self, name=None):
        super().__init__()
        self.name = name
        self.env_dir = f'{Thor.ENVIRONMENTS_DIR}/{self.name}'
        self.__env_list_cache = None
        self.__config = Config(f'{self.env_dir}/config.json')
        self.__saved_dir = None

    def aws_client(self, service):
        try:
            region = self.get_config().get('aws_region')
        except ConfigUnknownKeyException:
            error = 'aws_region not found in config.json. Exiting...'
            self.logger.error(error)
            exit(-1)
        profile = self.get_name()
        key = '{}.{}'.format(region, service)

        if key not in Env.__AWS_CLIENT_CACHE:
            aws = Aws(region, profile)
            Env.__AWS_CLIENT_CACHE[key] = aws.client(service)
        return Env.__AWS_CLIENT_CACHE[key]

    def is_valid(self):
        if os.path.exists(self.env_dir):
            return True
        else:
            return False

    def is_valid_or_exit(self):
        if not self.is_valid():
            self.logger.error(f'Invalid environment {self.name}')
            exit(-1)

    def is_valid_or_exception(self):
        if not self.is_valid():
            raise EnvNotFoundException(self.env_dir)

    def list(self):
        try:
            dirs = os.listdir(path=Thor.ENVIRONMENTS_DIR)
            return dirs
        except FileNotFoundError:
            raise EnvInvalidDirException(Thor.ENVIRONMENTS_DIR)

    def create(self):
        try:
            env_read_me_file = f'{self.env_dir}/README.txt'
            if os.path.exists(self.env_dir):
                raise EnvAlreadyExistsException(self.name)

            os.mkdir(path=self.env_dir)

            with open(env_read_me_file, mode='+x') as f:
                f.write('Environment {}'.format(self.name))
        except OSError as err:
            raise EnvCreationException(str(err))

    def get_config(self):
        return self.__config

    def get_name(self):
        return self.name

    def get_env_dir(self):
        return self.env_dir

    def get_variables_file(self):
        return f'{self.env_dir}/variables.json'

    def get_template_dir(self):
        return f'{self.env_dir}/templates'

    def get_template_files(self):
        if os.path.isdir(self.get_template_dir()):
            return list(os.walk(self.get_template_dir()))
        else:
            return []

    def __enter__(self):
        try:
            self.__saved_dir = os.getcwd()
            self.logger.info('cd %s', self.env_dir)
            os.chdir(self.env_dir)
            return self
        except Exception as err:
            self.logger.error(f'Cannot change dir to {self.env}')
            raise EnvException(str(err))

    def __exit__(self, type, value, traceback):
        self.logger.info(f'leaving directory {self.__saved_dir}')
        os.chdir(self.__saved_dir)
        self.__saved_dir = None

    def destroy(self):
        pass
