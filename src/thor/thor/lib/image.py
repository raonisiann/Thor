import json
import os
from thor.lib.base import Base
from thor.lib.config import Config
from thor.lib.aws_resources.parameter_store import (
    ParameterStore,
    ParameterStoreNotFoundException
)


class ImageException(Exception):
    pass


class ImageParams(object):

    RELATIVE_IMAGE_PARAMS = {
        'autoscaling_name': {
            'name': 'deploy/autoscaling_name',
            'type': ParameterStore.STRING_TYPE
        },
        'deploy_lock': {
            'name': 'deploy/lock',
            'type': ParameterStore.STRING_TYPE
        },
        'latest_ami_id': {
            'name': 'build/latest_ami_id',
            'type': ParameterStore.STRING_TYPE
        },
        'stabe_ami_id': {
            'name': 'build/stable_ami_id',
            'type': ParameterStore.STRING_TYPE
        },
        'ami_id_list': {
            'name': 'build/ami_id_list',
            'type': ParameterStore.STRING_LIST_TYPE
        }
    }

    def __init__(self, image, env):
        self.image_name = image
        self.env = env
        self.param = ParameterStore(env)
        self.__cache = {}

    def __getattr__(self, name):
        if name in ImageParams.RELATIVE_IMAGE_PARAMS:
            if name not in self.__cache:
                param_name = ImageParams.RELATIVE_IMAGE_PARAMS[name]['name']
                self.__cache[name] = self.__read_image_param_value(param_name)
            return self.__cache[name]
        else:
            raise AttributeError('Unknown attribute {}'.format(name))

    def __setattr__(self, name, value):
        if name in ImageParams.RELATIVE_IMAGE_PARAMS:
            param_name = ImageParams.RELATIVE_IMAGE_PARAMS[name]['name']
            param_type = ImageParams.RELATIVE_IMAGE_PARAMS[name]['type']
            self.__cache[name] = value
            self.__write_image_param_value(param_name, value, param_type)
        else:
            super().__setattr__(name, value)

    def __delattr__(self, name):
        if name in ImageParams.RELATIVE_IMAGE_PARAMS:
            self.param.destroy(self.__get_full_parameter_name(name))

    def __get_full_parameter_name(self, name):
        return '/thor/{env}/{image}/{param}'.format(
            env=self.env.get_name(),
            image=self.image_name,
            param=name
        )

    def __read_image_param_value(self, name):
        full_param_path = self.__get_full_parameter_name(name)
        try:
            param_value = self.param.get(full_param_path)
        except ParameterStoreNotFoundException:
            param_value = None
        return param_value

    def __write_image_param_value(self, name, value, param_type):
        full_param_path = self.__get_full_parameter_name(name)
        self.param.update_or_create(full_param_path, value, param_type)


class Image(Base):

    BUILD_FAIL_CODE = -1

    IMAGE_DIR_TEMPLATE = '{env_dir}/images/{name}'
    FILES_DIR_TEMPLATE = '{image_dir}/files'

    PACKER_FILE = 'packer.json'
    # parameters
    ASG_NAME_PARAM = '/{env}/{image}/deploy/asg_name'
    LATEST_AMI_BUILT_PARAM = '/{env}/{image}/build/latest/ami_id'
    LATEST_AMI_REGION_PARAM = '/{env}/{image}/build/latest/region'

    AMI_ID_LIST_MAX_SIZE = 10
    CONFIG_FILE_PATH = '{image_dir}/config.json'

    def __init__(self, env, name, aws_ami=None,
                 instance_type='t2.small'):
        super().__init__()
        self.name = name
        self.env = env
        self.aws_ami = aws_ami
        self.image_dir = None
        self.files_dir = None
        self.image_files_list = None
        self.instance_type = instance_type
        self.params = ImageParams(name, env)
        self.__config = Config(Image.CONFIG_FILE_PATH.format(
                               image_dir=self.get_image_dir()))
        self.__saved_dir = None

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
        self.clean_image_manifest_file()

    def clean_image_manifest_file(self):
        manifest_file_path = '{image_dir}/manifest.json'.format(
                              image_dir=self.get_image_dir())

        if os.path.exists(manifest_file_path):
            try:
                self.logger.info('Removing manifest file...')
                os.remove(manifest_file_path)
            except OSError:
                self.logger.warning('Fail to remove %s', manifest_file_path)

    def config(self):
        return self.__config

    def get_latest_ami_id(self):
        ami_id_string_list = self.params.ami_id_list
        if ami_id_string_list is not None:
            return ami_id_string_list[0]
        else:
            return None

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

    def rotate_ami_id_list(self, ami_id, ami_id_list):
        '''
        Rotate AMI string list making ami_id to apear at the
        begining of the list

        ami_id (str): ami-444444
        ami_id_list (list): [ami-333333, ami-222222, ami-11111]

        return (str): ami-444444,ami-333333,ami-222222,ami-11111
        '''
        if not ami_id_list or ami_id_list is None:
            return ami_id
        ami_id_list.insert(0, ami_id)
        return ','.join(ami_id_list[:Image.AMI_ID_LIST_MAX_SIZE])

    def update_ami_id(self, ami_id):
        ami_id_list = self.params.ami_id_list
        rotated_ami_string_list = self.rotate_ami_id_list(ami_id, ami_id_list)
        self.params.ami_id_list = rotated_ami_string_list
