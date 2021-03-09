#!/usr/bin/env python3

import argparse
import logging
from .__version__ import __version__
from . import (
    aws_instances,
    configure,
    deploy,
    env,
    infra,
    image,
    param,
    setup,
    stack
)

THOR_VERSION = __version__

SUB_MODULES = {
    'configure': {
        'help': 'Thor configuration',
        'entry': configure.main,
        'usage': 'thor configure SUBCOMMAND'
    },
    'deploy': {
        'help': 'Thor deploys',
        'entry': deploy.main,
        'usage': 'thor deploy SUBCOMMAND'
    },
    'env': {
        'help': 'Environment tools',
        'entry': env.main,
        'usage': 'thor env SUBCOMMAND'
    },
    'infra': {
        'help': 'Alias for terraform',
        'entry': infra.main,
        'usage': 'thor infra SUBCOMMAND'
    },
    'image': {
        'help': 'Manager application images with Packer',
        'entry': image.main,
        'usage': 'thor image SUBCOMMAND'
    },
    'instances': {
        'help': 'Manager AWS instances',
        'entry': aws_instances.main,
        'usage': 'thor instances SUBCOMMAND'
    },
    'param': {
        'help': 'Manage parameters on AWS SSM Parameter Store',
        'entry': param.main,
        'usage': 'thor param SUBCOMMAND'
    },
    'setup': {
        'help': 'Perform setup of Thor',
        'entry': setup.main,
        'usage': 'thor setup SUBCOMMAND'
    },
    'stack': {
        'help': 'Stack management for Thor',
        'entry': stack.main,
        'usage': 'thor stack SUBCOMMAND'
    }
}


def build_main_help_text():
    help_text = 'Thor {version}\n\n'.format(
        version=THOR_VERSION
    )
    help_text += 'Available Modules:\n\n'

    for name, value in SUB_MODULES.items():
        help_text += '  {name:<20} {help_text}\n'.format(
            name=name,
            help_text=value['help']
        )
    return help_text


def run():
    '''
    Thor main entry point
    ---------------------------------

    Parse arguments and run the specified module.

    You SHOULD NOT write any business logic here.
    '''

    logging.basicConfig(level=logging.INFO)

    main_parser = argparse.ArgumentParser(
        prog='thor',
        description='Thor Infrastructure Tools',
        add_help=False
    )

    main_parser.add_argument(
        'sub_module',
        type=str,
        nargs='?',
        help=build_main_help_text()
    )

    try:
        args, sub_module_args = main_parser.parse_known_args()
        func = SUB_MODULES[args.sub_module]['entry']
        func(sub_module_args)
    except KeyError:
        print(build_main_help_text())
