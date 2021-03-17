import argparse
from thor.lib.env import Env
from thor.lib.aws_resources.parameter_store import (
    ParameterStore,
    ParameterStoreException,
    ParameterStoreAlreadyExistsException,
    ParameterStoreNotFoundException
)


def get_param_path(env, name):
    return '/thor/{env}/{param}'.format(
        env=env.get_name(),
        param=name
    )


def create_param_cmd(args):
    param_path = get_param_path(args.env, args.name)
    param = ParameterStore(args.env)

    try:
        param_value = input('Enter Param value: ')
    except KeyboardInterrupt:
        print('\nCancelled by user')
        exit(1)
    print('Creating param {}'.format(args.name))

    try:
        param.create(param_path, param_value)
        print('Parameter created successful.')
    except ParameterStoreAlreadyExistsException:
        print('Parameter already exists.')
    except ParameterStoreException as err:
        print(str(err))


def delete_param_cmd(args):
    param_path = get_param_path(args.env, args.name)
    param = ParameterStore(args.env)

    if not args.no_safety:
        print('Confirm parameter deletion. Use --no-safety to avoid prompts.')
        proceed = input('Are you sure? [default no] ')

        if not proceed == 'yes':
            print('Operation cancelled.')
            exit(-1)
    try:
        param.destroy(param_path)
        print('Parameter {} deleted.'.format(args.name))
    except ParameterStoreNotFoundException:
        print('Parameter not found.')


def describe_param_cmd(args):
    param_path = get_param_path(args.env, args.name)
    param = ParameterStore(args.env)

    try:
        details = param.read(param_path)
        if details:
            for attr, value in details.items():
                print('{} = {}'.format(attr, value))
    except ParameterStoreNotFoundException:
        # we don't want to print anything if parameter doesnt exist.
        pass


def get_param_cmd(args):
    param_path = get_param_path(args.env, args.name)
    param = ParameterStore(args.env)

    try:
        param_value = param.get(param_path)
        print(param_value)
    except ParameterStoreNotFoundException:
        # we don't want to print anything if parameter doesnt exist.
        pass


def list_param_cmd(args):
    param = ParameterStore(args.env)
    param_path = get_param_path(args.env, '')

    for param in param.list(param_path):
        print('{}'.format(param['Name']))


def update_param_cmd(args):
    param_path = get_param_path(args.env, args.name)
    param = ParameterStore(args.env)

    try:
        param_value = input('Enter new value: ')
    except KeyboardInterrupt:
        print('\nCancelled by user')
        exit(1)
    print('Updating param {}...'.format(args.name))

    try:
        param.update(param_path, param_value)
    except ParameterStoreNotFoundException:
        print('Param not found')
    except ParameterStoreException as err:
        print(str(err))


def main(args):
    '''
    Param module entry point
    '''
    param_arg_parser = argparse.ArgumentParser(
        prog='thor param',
        description='Thor Parameter manager'
    )
    # request env for all parameter operations
    param_arg_parser.add_argument(
        '--env',
        metavar='ENVIRONMENT',
        required=True,
        type=str,
        help='Environent. Run "thor env list" to show available options.'
    )
    subparsers = param_arg_parser.add_subparsers()
    # create sub-command
    create_subparser = subparsers.add_parser(
        'create',
        help='Create a new parameter',
        usage='thor param create NAME'
    )
    create_subparser.add_argument(
        'name',
        metavar='NAME',
        type=str,
        help='Parameter name in format application/param. Ex.: db/port',
    )
    create_subparser.set_defaults(func=create_param_cmd)
    # list sub-command
    list_subparser = subparsers.add_parser(
        'list',
        help='List parameters',
        usage='thor param list'
    )
    list_subparser.set_defaults(func=list_param_cmd)
    # describe sub-command
    describe_subparser = subparsers.add_parser(
        'describe',
        help='Describe parameter value and all its properties',
        usage='thor param describe NAME',
    )
    describe_subparser.add_argument(
        'name',
        metavar='NAME',
        type=str,
        help='Parameter name in format application/param. Ex.: db/port',
    )
    describe_subparser.set_defaults(func=describe_param_cmd)
    # delete sub-command
    delete_subparser = subparsers.add_parser(
        'delete',
        help='Delete parameter',
        usage='thor param delete NAME',
    )
    delete_subparser.add_argument(
        'name',
        metavar='NAME',
        type=str,
        help='Parameter name in format application/param. Ex.: db/port',
    )
    delete_subparser.add_argument(
        '--no-safety',
        action='store_true',
        help='Does not request for confirmation when deleting paramenter',
    )
    delete_subparser.set_defaults(func=delete_param_cmd)
    # get sub-command
    get_subparser = subparsers.add_parser(
        'get',
        help='Get parameter value',
        usage='thor param get NAME',
    )
    get_subparser.add_argument(
        'name',
        metavar='NAME',
        type=str,
        help='Parameter name in format application/param. Ex.: db/port',
    )
    get_subparser.set_defaults(func=get_param_cmd)
    # update sub-command
    update_subparser = subparsers.add_parser(
        'update',
        help='Update parameter value',
        usage='thor param update NAME',
    )
    update_subparser.add_argument(
        'name',
        metavar='NAME',
        type=str,
        help='Parameter name in format application/param. Ex.: db/port',
    )
    update_subparser.set_defaults(func=update_param_cmd)

    args = param_arg_parser.parse_args(args)
    e = Env(args.env)
    e.is_valid_or_exit()

    if 'func' in args:
        args.env = e
        args.func(args)
    else:
        param_arg_parser.print_usage()
        exit(-1)
