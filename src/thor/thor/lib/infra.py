import argparse
import os
from thor.lib import cmd
from thor.lib.env import Env


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
