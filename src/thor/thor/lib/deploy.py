import abc
import logging
from datetime import datetime
from thor.lib.aws_resources.autoscaling import AutoScaling
from thor.lib.aws_resources.launch_template import LaunchTemplate
from thor.lib.aws_resources.parameter_store import (
    ParameterStore,
    ParameterStoreAlreadyExistsException
)
from thor.lib.base import Base
from thor.lib.env import Env
from thor.lib.image import Image
from thor.lib.utils.names_generator import random_string


class DeployException(Exception):
    pass


class DeployLockException(Exception):
    pass


class DeployLockAlreadyAcquiredException(Exception):
    pass


class Deploy(Base):

    __metaclass__ = abc.ABCMeta

    def __init__(self, image):
        super().__init__()
        self.image = image
        self.asg_settings = DeployAutoScalingConfig(image)
        self.__asg_client = None
        self.current_state = {}
        self.created_resources = []

    @abc.abstractmethod
    def abort(self):
        return


class DeployLock(Base):

    LOCK_PARAM = '/{env}/{image}/deploy/lock'
    LOCK_TEMPLATE = 'owner={owner},timestamp={timestamp}'

    def __init__(self, image):
        super().__init__()
        self.image = image
        self.param = ParameterStore(image.env)
        self.lock = ''

    def __get_lock_param(self):
        return DeployLock.LOCK_PARAM.format(
            env=self.image.env.Name(),
            image=self.image.Name()
        )

    def __generate_lock_info(self):
        timestamp = datetime.now().timestamp()
        owner = 'unknown'
        return DeployLock.LOCK_TEMPLATE.format(
            owner=owner,
            timestamp=timestamp
        )

    def read_lock_info(self):
        return self.param.read(self.__get_lock_param())

    def acquire(self):
        self.logger.info('Acquiring...')
        self.lock = self.__generate_lock_info()

        try:
            self.param.create(self.__get_lock_param(), self.lock)
            return self
        except ParameterStoreAlreadyExistsException:
            self.logger.error('Lock already acquired')
            raise DeployLockAlreadyAcquiredException()

    def release_force(self):
        self.param.destroy(self.__get_lock_param())

    def release(self):
        self.logger.info('Releasing...')
        if self.lock:
            self.param.destroy(self.__get_lock_param())
            self.lock = ''

    def __enter__(self):
        return self.acquire()

    def __exit__(self, type, value, traceback):
        self.release()


class DeployAutoScalingConfig:

    def __init__(self, image):
        self.__image = image
        self.description = ""
        self.ami_id = ""
        self.instance_type = ""
        self.key_pair = ""
        self.availability_zone_names = []
        self.subnet_ids = []
        self.lb_target_group = ""
        self.health_check = None
        self.min_capacity = 1
        self.max_capacity = 1
        self.desired_capacity = 1

    def __load_config(self):
        asg_settings = self.__image.env.config().get('auto_scaling_settings')
        for name, value in asg_settings.items():
            if name in self.__dict__:
                self.__setattr__(name, value)
            else:
                print('WARNING: Invalid config "{}"'.format(name))

    def generate_asg_name(self):
        template_name = 'ASG_{image}_{env}_{random}'
        return template_name.format(
            image=self.image.get_name(),
            env=self.image.env.get_name(),
            random=random_string()
        )

    def generate_config_dict(self):
        config_dict = {}
        for name, value in self.__dict__:
            if value:
                config_dict[name] = value
        return config_dict


class DeployBlueGreen(Deploy):

    def __init__(self, image):
        super().__init__(image)

    def abort(self):
        print('Aborting deploy...')
        exit(-1)

    def do_blue_green_deploy(self, image, ami_id, asg_name):

        try:
            cur_asg = self.get_auto_scaling_group_by_name(asg_name)

            if not cur_asg:
                print('No auto scaling groups were found')
                self.do_blue_green_deploy_abort()

            if not cur_asg['DesiredCapacity'] > 0:
                print('Desired capacity must be greater than 0.')
                self.do_blue_green_deploy_abort()

            cur_lt = self.get_launch_template_by_name(
                cur_asg['LaunchTemplate']['LaunchTemplateName']
            )

            print('ASG ' + cur_asg['AutoScalingGroupName'])
            print('  MinSize --> ' + str(cur_asg['MinSize']))
            print('  MaxSize --> ' + str(cur_asg['MaxSize']))
            print('  Desired capacity --> ' + str(cur_asg['DesiredCapacity']))
            print('  Launch template --> ' + str(cur_lt['LaunchTemplateName']))

            # create new launch configuration
            new_lt_name = 'LT_{env}_{image}_{rand}'.format(
                env=self.image.env.Name(),
                image=image,
                rand=datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
            )

            new_lt_data = cur_lt['LaunchTemplateData']
            new_lt_data['ImageId'] = ami_id
            new_lt_id = self.create_launch_template(new_lt_name, new_lt_data)

            # create new auto scaling group
            new_asg_data = {}
            new_asg_name = 'ASG_{env}_{image}_{rand}'.format(
                env=self.image.env.Name(),
                image=image,
                rand=datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
            )
            # items that must be ignored during asg
            # creation
            ignore_asg_data = [
                'AutoScalingGroupARN',
                'AutoScalingGroupName',
                'CreatedTime',
                'LaunchTemplate',
                'Instances'
            ]

            for name, value in cur_asg.items():
                if name in ignore_asg_data:
                    continue
                if type(value) == list and len(cur_asg[name]) == 0:
                    continue

                new_asg_data[name] = value

            new_asg_data['AutoScalingGroupName'] = new_asg_name
            new_asg_data['LaunchTemplate'] = {
                'LaunchTemplateName': new_lt_id,
                'Version': '$Latest'
            }

            self.create_auto_scaling_group(new_asg_data)

            self.wait_for_desired_capacity(
                asg_name=new_asg_name,
                desired_capacity=cur_asg['DesiredCapacity'],
                wait_seconds=30
            )

            self.terminate_auto_scaling_group(asg_name)
            print('Deploy SUCCESSFUL')
            return new_asg_name
        except KeyboardInterrupt:
            print('Deploy CANCELLED by user')
            self.do_blue_green_rollback()
        except DeployException as err:
            print('Something went wrong. {}'.format(str(err)))
            self.do_blue_green_rollback()
            print('Deploy FAILED')

    def do_blue_green_rollback(self):
        print('Running rollback actions...')

        for resource in self.created_resources:

            if resource['name'] == 'launch_template':
                self.delete_launch_template(resource['data'])
            if resource['name'] == 'auto_scaling_group':
                self.terminate_auto_scaling_group(resource['data'])
