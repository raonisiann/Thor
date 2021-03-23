import os
from thor.lib.aws import Aws
from thor.lib.base import Base
from thor.lib.config import Config


class EnvException(Exception):
    pass


class Env(Base):

    ROOT_FOLDER = '{}/environments'.format(os.getcwd())
    CONFIG_FILE_PATH = '{env_dir}/config.json'

    __AWS_CLIENT_CACHE = {}

    def __init__(self, name=None):
        super().__init__()
        self.name = name
        self.path = '{base}/{env}'.format(
            base=Env.ROOT_FOLDER,
            env=self.name
        )
        self.__env_list = []
        self.__config = Config(Env.CONFIG_FILE_PATH.format(env_dir=self.path))
        self.__saved_dir = None

    def config(self):
        return self.__config

    def Name(self):
        return self.name

    def Path(self):
        return self.path

    def aws_client(self, service):
        region = self.config().get('aws_region')
        profile = self.get_name()
        key = '{}.{}'.format(region, service)

        if key not in Env.__AWS_CLIENT_CACHE:
            aws = Aws(region, profile)
            Env.__AWS_CLIENT_CACHE[key] = aws.client(service)
        return Env.__AWS_CLIENT_CACHE[key]

    def is_valid(self):
        if self.name is None:
            return False
        environments = self.list()

        if self.name in environments:
            return True
        else:
            return False

    def is_valid_or_exit(self):
        if not self.is_valid():
            print('Invalid environment {}'.format(self.name))
            exit(-1)

    def is_valid_or_exception(self):
        if not self.is_valid():
            raise EnvException('Invalid environment {}'.format(self.name))

    def list(self):
        if self.__env_list:
            return self.__env_list

        try:
            dirs = os.listdir(path=Env.ROOT_FOLDER)
        except FileNotFoundError:
            print('Invalid environment dir "{}"'.format(Env.ROOT_FOLDER))
            exit(-1)

        for name in dirs:
            self.__env_list.append(name)
        return self.__env_list

    def create(self):
        try:
            env_read_me_file = '{env_path}/README.txt'.format(
                env_path=self.path
            )

            if os.path.exists(self.path):
                raise Exception('Environment {} already exists.'.format(
                    self.name
                ))

            os.mkdir(path=self.path)

            with open(env_read_me_file, mode='+x') as f:
                f.write('Environment {}'.format(self.name))

        except OSError as err:
            raise err

    def get_name(self):
        return self.name

    def get_env_path(self):
        return self.path

    def get_env_dir(self):
        return self.path

    def get_variables_file(self):
        return '{env_dir}/variables.json'.format(
            env_dir=self.get_env_dir()
        )


    def __enter__(self):
        self.__saved_dir = os.getcwd()
        env_dir = self.get_env_path()

        try:
            self.logger.info('cd %s', env_dir)
            os.chdir(env_dir)
            return self
        except Exception as err:
            raise EnvException('Cannot change dir to {} with error {}'.format(
                env_dir,
                str(err)
            ))

    def __exit__(self, type, value, traceback):
        self.logger.info('leaving directory %s', self.__saved_dir)
        os.chdir(self.__saved_dir)
        self.__saved_dir = None

    def destroy(self):
        pass
