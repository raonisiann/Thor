#!/usr/bin/env python3

import argparse
import json
import os
import sys

from . import cmd
from .env import Env
from .aws_ami_finder import AwsAmiFinder
from .packer import Packer
from .param import Param


class ImageException(Exception):
    pass


class Image:

    BUILD_FAIL_CODE = -1

    IMAGE_DIR_TEMPLATE = '{env_dir}/images/{name}'
    FILES_DIR_TEMPLATE = '{image_dir}/files'

    PACKER_FILE = 'packer.json'
    # parameters
    ASG_NAME_PARAM = '/{env}/{image}/deploy/asg_name'
    LATEST_AMI_BUILT_PARAM = '/{env}/{image}/build/latest/ami_id'
    LATEST_AMI_REGION_PARAM = '/{env}/{image}/build/latest/region'

    def __init__(self, env, name, aws_ami=None,
                 instance_type='t2.small'):
        self.name = name
        self.env = env
        self.aws_ami = aws_ami
        self.image_dir = None
        self.files_dir = None
        self.image_files_list = None
        self.instance_type = instance_type
        self.__saved_dir = None

    def get_asg_name(self):
        return Image.ASG_NAME_PARAM.format(
            env=self.env.Name(),
            image=self.name
        )

    def get_latest_ami_built_param(self):
        return Image.LATEST_AMI_BUILT_PARAM.format(
            env=self.env.Name(),
            image=self.name
        )

    def get_latest_ami_region_param(self):
        return Image.LATEST_AMI_REGION_PARAM.format(
            env=self.env.Name(),
            image=self.name
        )

    def get_ssh_username(self):
        ami_name = self.aws_ami['Name'].lower()

        if 'ubuntu' in ami_name:
            return 'ubuntu'
        elif 'amzn-ami' in ami_name:
            return 'ec2-user'

    def get_name(self):
        return self.name

    def Name(self):
        return self.name

    def get_image_dir(self):

        if self.image_dir is None:
            self.image_dir = '{env_dir}/images/{name}'.format(
                env_dir=self.env.get_env_path(),
                name=self.name
            )
        return self.image_dir

    def get_files_dir(self):

        if self.files_dir is None:
            self.files_dir = '{image_dir}/files'.format(
                image_dir=self.get_image_dir()
            )
        return self.files_dir

    def __get_image_files_list_rec(self, path, file_list):

        for file_name in os.listdir(path):
            file_path = '{base_dir}/{file_name}'.format(
                base_dir=path,
                file_name=file_name
            )
            if os.path.isdir(file_path):
                self.__get_image_files_list_rec(file_path, file_list)
            else:
                file_list.append(file_path)

    def get_image_files_list(self):

        if self.image_files_list is None:
            parsed_image_files = []
            files_dir = self.get_files_dir()

            if os.path.exists(files_dir):
                image_files = []
                self.__get_image_files_list_rec(files_dir, image_files)

            for image_file in image_files:
                parsed_image_files.append({
                    'src': './files{}'.format(image_file[len(files_dir):]),
                    'dst': image_file[len(files_dir):],
                })
            self.image_files_list = parsed_image_files
        return self.image_files_list

    def generate_packer_builder(self):
        ami_name = '{name}-base-{timestamp}'.format(
            name=self.name,
            timestamp='{{timestamp}}'
        )
        ami_description = '{name} Image. Based on : {base_ami}'.format(
            name=self.name,
            base_ami=self.aws_ami['Name']
        )
        # packer build section
        builder = [
            {
                'type': 'amazon-ebs',
                'ami_name': ami_name,
                'ami_description': ami_description,
                'region': self.env.get_config('aws_region'),
                'instance_type': self.instance_type,
                'source_ami': self.aws_ami['ImageId'],
                'communicator': "ssh",
                'ssh_username': self.get_ssh_username(),
                'tags': {
                    'base_ami_name': self.aws_ami['Name'],
                    'base_ami_id': self.aws_ami['ImageId'],
                    'build_date': '{{timestamp}}',
                    'env': self.env.Name(),
                    'image': self.get_name(),
                    'thor': '0.1',
                }
            }
        ]
        return builder

    def generate_packer_file(self):
        provisioners = []
        # add post-provisioner script
        provisioners.append(
            {
                'type': 'shell',
                'script': './pre_provisioner.sh',
                'remote_folder': '/tmp',
                'environment_vars': [
                    'IMAGE_NAME={}'.format(self.name)
                ]
            }
        )
        # add provisioner files
        for f in self.get_image_files_list():
            provisioners.append({
                'type': 'file',
                'source': f['src'],
                'destination': f['dst']
            })
        # add post-provisioner script
        provisioners.append(
            {
                'type': 'shell',
                'script': './post_provisioner.sh',
                'remote_folder': '/tmp',
                'environment_vars': [
                    'IMAGE_NAME={}'.format(self.name)
                ]
            }
        )
        # packer content
        packer_content = {
            'builders': self.generate_packer_builder(),
            'provisioners': provisioners
        }
        return json.dumps(packer_content, indent=4)

    def generate_instance_launch_script(self):
        # placed under : /var/lib/cloud/scripts/per-instance
        content = [
            '#!/usr/bin/env python3',
            'import random',
            'import os',
            '',
            'base_name = \'{image_name}\''.format(image_name=self.get_name()),
            'rand_size = 8',
            'rand_list = []',
            'char_pool = \'0123456789abcdefghijklmnopqrstuvwxyz\'',
            '',
            'for i in range(rand_size):',
            '    rand_list.append(random.choice(char_pool))',
            '',
            'host_name = \'{base}-{rand}\'.format(',
            '    base=base_name,',
            '    rand=\'\'.join(rand_list)',
            ')',
            '',
            'print(\'setting hostname to --->> {}\'.format(host_name))',
            '',
            'os.system(r\'hostnamectl set-hostname {}\'.format(host_name))',
            'os.system(r\'sed --in-place "s/127.0.0.1\\slocalhost/127.0.0.1 localhost {}/" /etc/hosts\'.format(host_name)) # noqa: E501, W605',
            '',
        ]
        return '\n'.join(content)

    def generate_pre_provisioner_file(self):
        mkdir_list = []

        for f in self.get_image_files_list():
            dir_name = os.path.dirname(f['dst'])
            mkdir_list.append(
                r'mkdir -p {dir_name}'.format(dir_name=dir_name)
            )
        content = [
            r'#!/bin/bash',
            r'',
            r'# pre-provisioner script',
        ]

        for mkdir_item in mkdir_list:
            content.append(mkdir_item)

        return '\n'.join(content)

    def generate_post_provisioner_file(self):
        content = [
            r'#!/bin/bash',
            r'',
            r'# post-proviosioner script',
            r'TZ="America/Sao_Paulo"',
            r'sudo ln -sf /usr/share/zoneinfo/$TZ /etc/localtime',
            r'echo $TZ | sudo tee /etc/timezone',
            r'',
            r''
        ]
        return '\n'.join(content)

    def get_latest_build(self, builds):
        latest = builds[0]

        for build in builds:
            if build['build_time'] > latest['build_time']:
                latest = build
        return latest

    def get_manifest_artifact_id(self):
        manifest_content = self.get_manifest_file_content()

        if 'builds' not in manifest_content:
            raise ImageException('No builds found on manifest file.')

        if len(manifest_content['builds']) > 1:
            latest_build = self.get_latest_build(manifest_content['builds'])
        else:
            latest_build = manifest_content['builds'][0]

        if 'artifact_id' not in latest_build:
            raise ImageException('No artifact found on manifest file.')

        return latest_build['artifact_id']

    def get_manifest_file_content(self):
        manifest_file = '{image_dir}/manifest.json'.format(
            image_dir=self.get_image_dir()
        )
        manifest_content = ""

        if os.path.exists(manifest_file):
            with open(manifest_file) as manifest:
                manifest_content = manifest.read()

        return json.loads(manifest_content)

    def __enter__(self):
        self.__saved_dir = os.getcwd()
        image_dir = self.get_image_dir()

        try:
            os.chdir(image_dir)
            return self
        except Exception as err:
            raise ImageException(
                'Cannot change dir to {} with error {}'.format(
                    image_dir,
                    str(err)
                )
            )

    def __exit__(self, type, value, traceback):
        os.chdir(self.__saved_dir)
        self.__saved_dir = None


def build_cmd(args):
    print('Building... ')
    packer_exec = Packer().get_exec_path()

    with Image(args.env, args.image, None) as img:
        print('Changing directory to {}'.format(img.get_image_dir()))
        # $ packer build TEMPLATE
        packer_cmd = [
            '{packer_exec}'.format(packer_exec=packer_exec),
            'build',
            '{}'.format(Image.PACKER_FILE)
        ]
        # run packer build
        result = cmd.run_interactive(packer_cmd)
        print('Build return code ===>>> {}'.format(result))

        if result == 0:
            if args.update_latest_ami:
                print('Updating parameter store...')
                print('Getting latest built artifact...')
                try:
                    artifact_id = img.get_manifest_artifact_id()
                    region, ami_id = artifact_id.split(':')
                except ValueError:
                    print('BUILD ERROR: Invalid manifest ID ==> {}'.format(
                        artifact_id
                    ))

                ami_id_param = img.get_latest_ami_built_param()
                region_param = img.get_latest_ami_region_param()

                ps = Param(args.env)

                try:
                    print('Updating --> {}'.format(ami_id_param))
                    ps.update_param(ami_id_param, ami_id)
                    print('Updating --> {}'.format(region_param))
                    ps.update_param(region_param, region)
                except Exception as err:
                    print('Param update FAIL with error: {}'.format(
                        str(err)
                    ))
                    exit(Image.BUILD_FAIL_CODE)
            print('BUILD FINISHED WITH SUCCESS')
        else:
            print('BUILD FINISHED WITH ERRORS')
            exit(Image.BUILD_FAIL_CODE)


def describe_cmd(args):
    pass


def generate_cmd(args):
    print('Generating settings...', file=sys.stderr)
    aws_filters = ''
    env = args.env

    if 'filters' in args:
        aws_filters = args.filters

    ami_finder = AwsAmiFinder(env.get_config('aws_region'))
    latest_image = ami_finder.get_latest_image(aws_filters)
    if latest_image:
        img = Image(env, args.image, latest_image)
        print('Packer file ===============')
        print(img.generate_packer_file())
        print('Pre-Provisioner script ========')
        print(img.generate_pre_provisioner_file())
        print('Post-Provisioner script ========')
        print(img.generate_post_provisioner_file())
        print('Instance launch script ====')
        print(img.generate_instance_launch_script())
    else:
        print('No images found with selected filters.')


def main(args):
    '''
    Image module entry point
    '''
    ami_arg_parser = argparse.ArgumentParser(
        prog='Automator image',
        description='Automator AWS Image Manager'
    )

    # request env for all parameter operations
    ami_arg_parser.add_argument(
        '--env',
        metavar='ENVIRONMENT',
        required=True,
        type=str,
        help='Environent. Run "thor env list" to show available options.'
    )
    # request image for all parameter operations
    ami_arg_parser.add_argument(
        '--image',
        metavar='IMAGE',
        required=True,
        type=str,
        help='Image. Run "thor image --env=$ENV list"'
             'to show available options.'
    )
    # allow set aws region if unable to auto detect
    ami_arg_parser.add_argument(
        '--aws-region',
        metavar='AWS_REGION',
        required=False,
        type=str,
        help='AWS Region'
    )
    # allow set ami filters to AMI lookup
    ami_arg_parser.add_argument(
        '--filters',
        metavar='name=value[,name=value]',
        required=False,
        type=str,
        help='AMI Filters for image lookup. Format: key=value'
             'If multiple filters use comma: a=1,b=2'
    )

    subparsers = ami_arg_parser.add_subparsers()
    # build sub-command
    build_subparser = subparsers.add_parser(
        'build',
        help='image build ENV',
        usage='image build ENV'
    )
    build_subparser.add_argument(
        '--update-latest-ami',
        action='store_true',
        required=False
    )
    build_subparser.set_defaults(func=build_cmd)
    # describe sub-command
    describe_subparser = subparsers.add_parser(
        'describe',
        help='Describe settings on Packer',
        usage='Describe action must be either current or backup.',
    )
    describe_subparser.set_defaults(func=describe_cmd)
    # generate sub-command
    generate_subparser = subparsers.add_parser(
        'generate',
        help='Generate new Packer configuration based on entered arguments'
    )
    generate_subparser.add_argument(
        '--write',
        help='Write generated content in the packer file.'
             'Backups the existing one.'
    )
    generate_subparser.set_defaults(func=generate_cmd)

    args = ami_arg_parser.parse_args(args)
    e = Env(args.env)
    e.is_valid_or_exit()

    if args.aws_region:
        print('Overriding AWS Region with = {}'.format(args.aws_region))
        e.set_config('aws_region', args.aws_region)

    if 'func' in args:
        args.env = e
        args.func(args)
    else:
        ami_arg_parser.print_usage()
        exit(-1)
