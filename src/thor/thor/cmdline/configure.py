import argparse
from thor.lib import cmd
from thor.lib.env import Env


def configure_aws_credentials(profile):

    aws_configure = 'aws configure --profile {}'.format(profile)
    print('Running: {}'.format(aws_configure))
    cmd.run_interactive(aws_configure)


def configure_credentials_cmd(args):
    print('configuring credentials...')
    configure_aws_credentials(args.env)


def configure_default_cmd(args):
    configure_aws_credentials(args.env)


def main(args):
    '''
    Configure entry point
    '''
    configure_parser = argparse.ArgumentParser(
        prog='Thor configure',
        description='Thor configure'
    )
    # request env for all parameter operations
    configure_parser.add_argument(
        '--env',
        metavar='ENVIRONMENT',
        required=True,
        type=str,
        help='Environent. Run "thor env list" to show available options.'
    )

    configure_parser.add_argument(
        '--credentials',
        required=False,
        action='store_true',
        help='Prompt only for credential related settings.'
    )

    args = configure_parser.parse_args(args)
    e = Env(args.env)
    e.is_valid_or_exit()

    if args.credentials:
        configure_credentials_cmd(args)
    else:
        configure_default_cmd(args)
