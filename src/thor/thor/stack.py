import argparse
import os
import shutil

STACK_BASE_PATH = '{base}/src/stack'.format(base=os.getcwd())
STACK_AVAILABLE_PATH = '{base}/available'.format(base=STACK_BASE_PATH)
STACK_SKELETON_PATH = '{base}/skeleton'.format(base=STACK_BASE_PATH)

STACK_SKELETON = {
    'provisioner.sh': '#!/bin/bash',
    'README.txt': '',
}


def list_stack(args):
    print('Available Stacks:')

    try:
        dirs = os.listdir(path=STACK_AVAILABLE_PATH)
        for name in dirs:
            print(' - {}'.format(name))
    except FileNotFoundError:
        print('Unable to locate stack dir')


def create_stack(args):
    if 'stack_name' in args:
        print('Creating stack {}'.format(args.stack_name), end='...')
        try:
            stack_path = '{stack_path}/{stack_name}'.format(
                stack_path=STACK_AVAILABLE_PATH,
                stack_name=args.stack_name
            )
            if os.path.isdir(stack_path):
                print('Already exists')
            else:
                os.mkdir(stack_path)
                print('Done')
                shutil.copytree(STACK_SKELETON_PATH, stack_path)
        except OSError as err:
            raise Exception('Fail to create stack with error: ', str(err))


def destroy_stack(args):
    print(args)
    if 'stack_name' in args:
        print('Destroying stack {}'.format(args.stack_name), end='...')
        try:
            stack_path = '{stack_path}/{stack_name}'.format(
                stack_path=STACK_AVAILABLE_PATH,
                stack_name=args.stack_name
            )
            if os.path.isdir(stack_path):
                shutil.rmtree(stack_path)
                print('Done')
            else:
                print('Unknown stack')
        except OSError as err:
            raise Exception('Fail to create stack with error: ', str(err))


def main(args):
    '''
    Setup entry point
    '''
    setup_parser = argparse.ArgumentParser(
        prog='Thor Stack',
        description='''
    Thor Stack module is used to maintain configuration files for 
    each stack of this project.

    All stack configuration files are kept under src/stack.

    !!!Thor stack doesn't perform any changes in the infrastructure!!!
        '''
    )

    subparsers = setup_parser.add_subparsers()
    # create sub-command
    create_subparser = subparsers.add_parser(
        'create',
        help='Create all required files to add a new stack',
        usage='thor stack create STACK_NAME'
    )
    create_subparser.add_argument(
        'stack_name',
        metavar='stack_name',
        type=str,
        help='Create configuration files for a new stack'
    )
    create_subparser.set_defaults(func=create_stack)
    # destroy sub-command
    destroy_subparser = subparsers.add_parser(
        'destroy',
        help='Destroy existing stack configuration files',
        usage='thor stack destroy STACK_NAME'
    )
    destroy_subparser.add_argument(
        'stack_name',
        metavar='stack_name',
        type=str,
        help='Destroy configuration files for a existing stack'
    )
    destroy_subparser.add_argument(
        '-f',
        type=str,
        help='Perform actions without asking. CAUTION!'
    )
    destroy_subparser.set_defaults(func=destroy_stack)
    # list sub-command
    list_subparser = subparsers.add_parser(
        'list',
        help='List existing stacks',
        usage='thor stack list'
    )
    list_subparser.set_defaults(func=list_stack)

    args = setup_parser.parse_args(args.subcommands)

    if 'func' in args:
        args.func(args)
    else:
        setup_parser.print_usage()
        exit(-1)
