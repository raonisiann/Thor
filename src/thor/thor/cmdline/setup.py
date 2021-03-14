import argparse
import requests
import os
import zipfile


# Assuming current working dir
# is the root of the project.
SETUP_DIRS = {
    'bin': '{}/bin'.format(os.getcwd()),
    'tmp': '{}/tmp'.format(os.getcwd())
}

HASHICORP_URL = 'https://releases.hashicorp.com'


PACKAGES = {
    'packer': {
        'download_url': 'https://releases.hashicorp.com/'
                        'packer/1.6.5/packer_1.6.5_linux_amd64.zip'
    },
    'terraform': {
        'download_url': 'https://releases.hashicorp.com/'
                        'terraform/0.14.0/terraform_0.14.0_linux_amd64.zip'
    }
}


def get_tmp_dir():
    return SETUP_DIRS['tmp']


def get_bin_dir():
    return SETUP_DIRS['bin']


def get_package_path(package):
    if package in PACKAGES:
        return '{base}/{package}'.format(
            base=SETUP_DIRS[package],
            package=package
        )
    raise Exception('Unable to get package {}.'.format(package))


def __create_dirs():
    for _, path in SETUP_DIRS.items():
        if os.path.exists(path):
            continue

        try:
            os.mkdir(path)
        except OSError as err:
            print(str(err))
            exit(-1)


def download(name, url):

    try:
        response = requests.get(
            url,
            allow_redirects=True
        )
    except Exception as err:
        raise Exception(
            'Fail to download {} with error: {}'.format(
                name,
                str(err)
            )
        )

    tmp_file = '{base}/{name}'.format(
        base=get_tmp_dir(),
        name=name
    )

    with open(tmp_file, 'wb') as download:
        try:
            download.write(response.content)
        except Exception as err:
            print('Unable to write content at {}'.format(tmp_file))
            print(str(err))

    return tmp_file


def clean_packages(args):

    for name, _ in PACKAGES.items():
        print('Cleaning {}'.format(name), end='...')
        bin_file = '{base_dir}/{file_name}'.format(
            base_dir=get_bin_dir(),
            file_name=name
        )

        if os.path.exists(bin_file):
            try:
                os.unlink(bin_file)
                print('Done')
            except Exception as err:
                print('Failed')
                raise Exception(
                    'Clean of {} failed with error {}'.format(
                        name,
                        str(err)
                    )
                )


def list_packages(args):
    print('Package list:')
    print('')

    for name, info in PACKAGES.items():
        print('  {} (source: {})'.format(
            name, info['download_url']
        ))


def install_packages(args):
    __create_dirs()

    for name, info in PACKAGES.items():
        print('Installing {} into {}'.format(
            name,
            get_bin_dir()
        ), end='...')
        file_name = download(name, info['download_url'])

        with zipfile.ZipFile(file_name, 'r') as z:
            z.extractall(get_bin_dir())

        if not os.path.exists('{}/{}'.format(get_bin_dir(), name)):
            print('Failed')
            raise Exception('Installation of {} failed'.format(name))
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
