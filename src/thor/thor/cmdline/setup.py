import argparse
import logging
import os
import zipfile
from thor.lib.executable import ExecutableDownloadAlreadyExists
from thor.lib.packer import Packer
from thor.lib.terraform import Terraform


TMP_DIR = '/tmp'
PACKAGES = [
    Packer(),
    Terraform()
]

logger = logging.getLogger('setup')


def __create_dirs():
    for obj in PACKAGES:
        if os.path.exists(obj.install_dir):
            continue
        try:
            os.mkdir(obj.install_dir)
        except OSError as err:
            logger.error(str(err))
            exit(-1)


def clean_packages(args):
    logger.info('Cleaning packages...')
    for obj in PACKAGES:
        exec_path = obj.get_exec_path()
        logger.info('Cleaning {}'.format(exec_path))

        if os.path.exists(exec_path):
            try:
                os.unlink(exec_path)
                logger.info('{} removed.'.format(obj.exec_name))
            except OSError as err:
                logger.error(str(err))
    logger.info('Cleaning done.')


def list_packages(args):
    for obj in PACKAGES:
        if os.path.exists(obj.get_exec_path()):
            print(obj.exec_name)


def install_packages(args):
    __create_dirs()

    for obj in PACKAGES:
        print('Installing {} into {}'.format(obj.exec_name, obj.install_dir),
              end='...')

        file_name = obj.download(TMP_DIR)

        with zipfile.ZipFile(file_name, 'r') as z:
            z.extractall(obj.install_dir)

        if not os.path.exists(obj.get_exec_path()):
            raise Exception('Installation of %s failed', obj.exec_path)
        print('Done')


def main(args):
    '''
    Setup entry point
    '''
    setup_parser = argparse.ArgumentParser(
        prog='Thor setup',
        description='Thor setup'
    )

    subparsers = setup_parser.add_subparsers()
    # clean sub-command
    clean_subparser = subparsers.add_parser(
        'clean',
        help='Clean installed packages under bin',
        usage='Clean installed packages under bin'
    )
    clean_subparser.set_defaults(func=clean_packages)
    # list sub-command
    list_subparser = subparsers.add_parser(
        'list',
        help='List packages used by this tool',
        usage='List packages used by this tool'
    )
    list_subparser.set_defaults(func=list_packages)
    # install sub-command
    install_subparser = subparsers.add_parser(
        'install',
        help='Install all packages used by this tool under $ROOT/bin',
        usage='Install all packages used by this tool under $ROOT/bin'
    )
    install_subparser.set_defaults(func=install_packages)

    args = setup_parser.parse_args(args)

    if 'func' in args:
        args.func(args)
    else:
        setup_parser.print_usage()
        exit(-1)
