import json
import os

from thor.lib.base import Base
from thor.lib.config import Config
from thor.lib.thor import Thor
from thor.lib.aws_resources.parameter_store import (
    ParameterStore,
    ParameterStoreNotFoundException
)


class ImageInvalidException(Exception):
    pass


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

    def __init__(self, image):
        self.image = image
        self.param = ParameterStore(self.image.env)
        self.cache = {}

    def __getattr__(self, name):
        if name in ImageParams.RELATIVE_IMAGE_PARAMS:
            if name not in self.cache:
                try:
                    value = self.param.get(self.get_param_path(name))
                    self.cache[name] = value
                except ParameterStoreNotFoundException:
                    self.cache[name] = None
            return self.cache[name]
        else:
            return self.__dict__[name]

    def __setattr__(self, name, value):
        if name in ImageParams.RELATIVE_IMAGE_PARAMS:
            self.param.update_or_create(self.get_param_path(name),
                                        value,
                                        self.get_param_type(name))
            self.cache[name] = value
        else:
            self.__dict__[name] = value

    def __delattr__(self, name):
        if name in ImageParams.RELATIVE_IMAGE_PARAMS:
            self.param.destroy(self.get_param_path(name))
            self.cache[name] = None
        else:
            del(self.__dict__[name])

    def get_param_path(self, name):
        param_name = ImageParams.RELATIVE_IMAGE_PARAMS[name]['name']
        return '/thor/{env}/{image}/{param}'.format(
            env=self.image.env.get_name(),
            image=self.image.get_name(),
            param=param_name
        )

    def get_param_type(self, name):
        return ImageParams.RELATIVE_IMAGE_PARAMS[name]['type']


class Image(Base):

    BUILD_FAIL_CODE = -1

    PACKER_FILE = 'packer.json'
    # parameters
    ASG_NAME_PARAM = '/{env}/{image}/deploy/asg_name'
    LATEST_AMI_BUILT_PARAM = '/{env}/{image}/build/latest/ami_id'
    LATEST_AMI_REGION_PARAM = '/{env}/{image}/build/latest/region'

    AMI_ID_LIST_MAX_SIZE = 10

    def __init__(self, env, name, aws_ami=None,
                 instance_type='t2.small'):
        super().__init__()
        self.name = name
        self.env = env
        self.aws_ami = aws_ami
        self.image_dir = f'{Thor.IMAGES_DIR}/{name}'
        self.template_dir = f'{self.image_dir}/templates'
        self.static_dir = f'{self.image_dir}/static'
        self.image_files_list = None
        self.instance_type = instance_type
        self.params = ImageParams(self)
        self.config = Config(f'{self.image_dir}/config.json')
        self.__saved_dir = None

    def __enter__(self):
        try:
            self.__saved_dir = os.getcwd()
            os.chdir(self.image_dir)
            return self
        except FileNotFoundError:
            raise ImageInvalidException(f'Invalid image {self.name}')

    def __exit__(self, type, value, traceback):
        os.chdir(self.__saved_dir)
        self.__saved_dir = None
        self.clean_image_manifest_file()

    def clean_image_manifest_file(self):
        manifest_file_path = f'{self.image_dir}/manifest.json'
        if os.path.exists(manifest_file_path):
            try:
                self.logger.info('Removing manifest file...')
                os.remove(manifest_file_path)
            except OSError:
                self.logger.warning('Fail to remove %s', manifest_file_path)

    def get_config(self):
        return self.config

    def get_latest_ami_id(self):
        ami_id_string_list = self.params.ami_id_list
        if ami_id_string_list is not None:
            return ami_id_string_list[0]
        else:
            return None

    def get_asg_name(self):
        return Image.ASG_NAME_PARAM.format(
            env=self.env.get_name(),
            image=self.name
        )

    def get_latest_ami_built_param(self):
        return Image.LATEST_AMI_BUILT_PARAM.format(
            env=self.env.get_name(),
            image=self.name
        )

    def get_latest_ami_region_param(self):
        return Image.LATEST_AMI_REGION_PARAM.format(
            env=self.env.get_name(),
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

    def get_variables_file(self):
        return f'{self.image_dir}/variables.json'

    def get_packer_file(self):
        packer_file = f'{self.image_dir}/packer.json'
        if os.path.exists(packer_file):
            return packer_file
        else:
            return ''

    def get_template_files(self):
        if os.path.isdir(self.template_dir):
            return list(os.walk(self.template_dir))
        else:
            return []

    def get_static_files(self):
        if os.path.isdir(self.static_dir):
            tree = os.walk(self.static_dir)
            return tree
        else:
            return []

    def get_static_dir(self):
        return self.static_dir

    def get_template_dir(self):
        return self.template_dir

    def get_image_dir(self):
        return self.image_dir

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
        manifest_file = 'manifest.json'
        manifest_content = ''

        if os.path.exists(manifest_file):
            with open(manifest_file, 'r') as manifest:
                manifest_content = manifest.read()
            return json.loads(manifest_content)
        else:
            self.logger.warning('No manifest file found')
            return ''

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
