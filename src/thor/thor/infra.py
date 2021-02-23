import argparse
import os
from .env import Env
from . import (
    cmd
)


class InfraException(Exception):
    pass


class Infra:

    def run_terraform(self, env, terraform_args):
        with Env(env) as e:
            tf_main_file = '{}/main.tf'.format(e.path)
            print('Running under {}'.format(e.path))

            if not os.path.exists(tf_main_file):
                print('No main.tf file defined. Nothing to do.')
                exit(-1)

            tf_command = 'terraform {tf_args}'.format(
                tf_args=' '.join(terraform_args)
            )

            cmd.run_interactive(tf_command)


def main(args):
    '''
    Infra module entry point
    '''
    infra_arg_parser = argparse.ArgumentParser(
        prog='thor infra',
        description='Thor Infra. This is just an '
                    'alias to run `terraform` using '
                    'correct enviroment.'
    )
    # request env for all parameter operations
    infra_arg_parser.add_argument(
        '--env',
        metavar='ENVIRONMENT',
        required=True,
        type=str,
        help='Environent. Run "thor env list" to show available options.'
    )

    args, terraform_args = infra_arg_parser.parse_known_args(args)
    e = Env(args.env)
    e.is_valid_or_exit()

    if 'env' in args:
        infra = Infra()
        infra.run_terraform(args.env, terraform_args)
    else:
        infra_arg_parser.print_usage()
        exit(-1)
