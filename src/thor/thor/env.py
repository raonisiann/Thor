import argparse
import json
import os
from .aws import Aws


class EnvException(Exception):
    pass


class Env:

    ROOT_FOLDER = '{}/environments'.format(os.getcwd())
    CONFIG_FILE_PATH = '{env_dir}/config.json'

    def __init__(self, name=None):
        self.config = {}
        self.name = name
        self.path = '{base}/{env}'.format(
            base=Env.ROOT_FOLDER,
            env=self.name
        )
        self.__saved_dir = None
        self.__load_config()

    def __load_config(self):
        config_file_path = self.get_config_file_path()
        config_json = ""

        if os.path.exists(self.get_config_file_path()):
            with open(config_file_path) as f:
                config_json = json.loads(f.read())

            for name, value in config_json.items():
                self.config[name] = value

    def Config(self):
        return self.config

    def Name(self):
        return self.name

    def Path(self):
        return self.path

    def aws_client(self, service):
        region = self.get_config('aws_region')
        profile = self.get_name()

        aws = Aws(region, profile)
        return aws.client(service)

    def get_config(self, name):

        if name in self.config:
            return self.config[name]

        return None

    def set_config(self, name, value):
        self.config[name] = value

    def is_valid(self):
        if self.name is None:
            return False

        environments = self.get_all()

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

    def get_all(self):
        env_list = []
        try:
            dirs = os.listdir(path=Env.ROOT_FOLDER)
            for name in dirs:
                env_list.append(name)
            return env_list
        except FileNotFoundError:
            print('Unable to locate env dir')

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

    def get_config_file_path(self):
        return Env.CONFIG_FILE_PATH.format(
            env_dir=self.get_env_path()
        )

    def __enter__(self):
        self.__saved_dir = os.getcwd()
        env_dir = self.get_env_path()

        try:
            os.chdir(env_dir)
            return self
        except Exception as err:
            raise EnvException('Cannot change dir to {} with error {}'.format(
                env_dir,
                str(err)
            ))

    def __exit__(self, type, value, traceback):
        os.chdir(self.__saved_dir)
        self.__saved_dir = None

    def destroy(self):
        pass


def list_env_cmd(args):
    env = Env()
    environments = env.get_all()
    for env in environments:
        print('{}'.format(env))


def create_env_cmd(args):
    print('Creating environment {}'.format(args.name))

    try:
        env = Env(args.name)
        env.create()
        print('Success! Environment created under: {}'.format(Env.ROOT_FOLDER))
        print('Make sure to commit your changes.')
    except Exception as err:
        print('Error: {}'.format(
            str(err)
        ))


def main(args):
    '''
    Environment module entry point
    '''
    env_arg_parser = argparse.ArgumentParser(
        prog='thor env',
        description='Thor Environment Tools'
    )

    subparsers = env_arg_parser.add_subparsers()
    # create sub-command
    create_subparser = subparsers.add_parser(
        'create',
        help='Create a new environment',
        usage='thor param env NAME'
    )
    create_subparser.add_argument(
        'name',
        metavar='NAME',
        type=str,
        help='Environment Name',
    )
    create_subparser.set_defaults(func=create_env_cmd)
    # list sub-command
    list_subparser = subparsers.add_parser(
        'list',
        help='List environments',
        usage='thor env list'
    )
    list_subparser.set_defaults(func=list_env_cmd)
    args = env_arg_parser.parse_args(args)

    if 'func' in args:
        args.func(args)
    else:
        env_arg_parser.print_usage()
        exit(-1)
