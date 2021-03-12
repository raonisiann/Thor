import argparse
from thor.lib.param import (
    Param,
    ParamException,
    ParamTypeNotSupportedException
)


def create_param_cmd(args):
    param_value = input('Enter Param value: ')
    p = Param(args.env)
    print('Creating param {}'.format(args.name))
    version = p.create_param(args.name, param_value, 'String')

    if version:
        print('Parameter created successful. Version {}'.format(version))
    else:
        print('Something went wrong while creating parameter')


def delete_param_cmd(args):
    p = Param(args.env)

    if args.no_safety:
        result = p.delete_param(args.name)
    else:
        print('Confirm parameter deletion. Use --no-safety to avoid prompts.')
        proceed = input('Are you sure? [default no] ')

        if proceed == 'yes':
            result = p.delete_param(args.name)
        else:
            print('Operation cancelled.')
            exit(-1)

    if result:
        print('Parameter {} deleted'.format(args.name))


def describe_param_cmd(args):
    p = Param(args.env)
    details = p.describe_param(args.name)

    if details:
        for attr, value in details.items():
            print('{} = {}'.format(attr, value))


def get_param_cmd(args):
    p = Param(args.env)
    param_value = p.get_param(args.name)
    print(param_value)


def list_param_cmd(args):
    p = Param(args.env)

    for param in p.list_param():
        print('{}'.format(param))


def update_param_cmd(args):
    print('Updating param {}...'.format(args.name))
    param_value = input('Enter new value: ')
    p = Param(args.env)
    current_param = p.describe_param(args.name)

    if current_param:
        new_version = p.update_param(args.name, param_value)

        if new_version:
            print('Parameter updated from {} --> {} version.'.format(
                current_param['Version'],
                new_version
            ))
        else:
            print('Something went wrong while updating parameter')
    else:
        print('Something went wrong while getting parameter')


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