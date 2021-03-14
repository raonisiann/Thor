import argparse
from thor.lib.env import Env


def list_env_cmd(args):
    env = Env()
    environments = env.list()
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
