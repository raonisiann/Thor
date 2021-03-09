#!/usr/bin/env python3
import abc
import argparse
import datetime
import time
from thor.utils.names_generator import random_string
from .env import Env
from .image import Image
from .param import Param
from .aws import Aws


class DeployException(Exception):
    pass


class DeployLockException(Exception):
    pass


class DeployLock:

    LOCK_PARAM = '/{env}/{image}/deploy/lock'
    LOCK_TEMPLATE = 'owner={owner},timestamp={timestamp}'

    def __init__(self, image):
        self.image = image
        self.param = Param(image.env)
        self.lock = ''

    def __get_lock_param(self):
        return DeployLock.LOCK_PARAM.format(
            env=self.image.env.Name(),
            image=self.image.Name()
        )

    def __generate_lock(self):
        timestamp = datetime.datetime.now().timestamp()
        owner = 'unknown'

        return DeployLock.LOCK_TEMPLATE.format(
            owner=owner,
            timestamp=timestamp
        )

    def get_lock(self):
        return self.param.get(self.__get_lock_param())

    def is_lock_acquired(self):
        has_lock = self.get_lock()

        if has_lock:
            return True
        else:
            return False

    def acquire(self):

        if not self.is_lock_acquired():
            return False

        generated_lock = self.__generate_lock()

        try:
            self.param.create(self.__get_lock_param(), generated_lock)
            self.lock = generated_lock
            return self.lock
        except Exception as err:
            ex_message = 'Unable to acquire lock with error: {}'.format(
                str(err)
            )
            raise DeployLockException(ex_message)

    def release_force(self):
        self.param.delete(self.__get_lock_param())

    def release(self):
        if self.lock:
            self.param.delete(self.__get_lock_param())
            self.lock = ''

    def __enter__(self):
        if self.is_lock_acquired():
            lock = self.get_lock()
            lock_exception = 'Lock already acquired => {}'.format(lock)
            raise DeployLockException(lock_exception)
        else:
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


class Deploy(object):

    __metaclass__ = abc.ABCMeta

    def __init__(self, image):
        self.image = image
        self.asg_settings = DeployAutoScalingConfig(image)
        self.__asg_client = None
        self.current_state = {}
        self.created_resources = []

    @abc.abstractmethod
    def abort(self):
        return


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


def deploy_cmd(args):
    print('Deploying...')

    img = Image(env=args.env, name=args.image)
    ps = Param(args.env)

    deploy = DeployBlueGreen(img)
    print(deploy.discover_auto_scaling_groups())

    exit()

    with DeployLock(img) as lock:
        print('Lock acquired: {}'.format(lock))

        try:
            latest_ami_param = img.get_latest_ami_built_param()
            latest_ami_region_param = img.get_latest_ami_region_param()
            asg_name_param = img.get_asg_name()

            latest_ami_id = ps.get_param(latest_ami_param)
            latest_ami_region = ps.get_param(latest_ami_region_param)
            asg_name = ps.get_param(asg_name_param)

            if not latest_ami_id:
                raise DeployException('Could not get latest AMI')

            if not asg_name:
                raise DeployException('Could not get Auto Scaling group')

            print('{} = {}'.format(latest_ami_param, latest_ami_id))
            print('{} = {}'.format(latest_ami_region_param, latest_ami_region))
            print('{} = {}'.format(asg_name_param, asg_name))

        except Exception as err:
            raise DeployException('Fail to get params with error: {}'.format(
                str(err)
            ))

        try:
            deploy = Deploy(img)
            # do blue/green deploy
            new_asg_name = deploy.do_blue_green_deploy(
                image=img.get_name(),
                ami_id=latest_ami_id,
                asg_name=asg_name
            )
            print('Updating AutoScaling group name...')
            ps.update_param(asg_name_param, new_asg_name)
            print('DEPLOY DONE.')
        except DeployException as err:
            print('Deploy FAIL with error: {}'.format(
                str(err)
            ))
            exit(-1)


def main(args):
    '''
    Deploy module entry point
    '''
    deploy_arg_parser = argparse.ArgumentParser(
        prog='Thor deploy',
        description='Thor deploy'
    )

    # request env for all parameter operations
    deploy_arg_parser.add_argument(
        '--env',
        metavar='ENVIRONMENT',
        required=True,
        type=str,
        help='Environent. Run "thor env list" to show available options.'
    )
    # allow to set aws region for all parameter operations
    deploy_arg_parser.add_argument(
        '--aws-region',
        metavar='AWS_REGION',
        required=False,
        type=str,
        help='AWS Region'
    )
    # request image for all parameter operations
    deploy_arg_parser.add_argument(
        '--image',
        metavar='IMAGE',
        required=True,
        type=str,
        help='Image. Run "thor image --env=$ENV list"'
             'to show available options.'
    )

    args = deploy_arg_parser.parse_args(args)
    e = Env(args.env)
    e.is_valid_or_exit()

    if args.aws_region:
        print('Overriding AWS Region with = {}'.format(args.aws_region))
        e.set_config('aws_region', args.aws_region)
    # inject environment object on arguments
    args.env = e
    # run deploy
    deploy_cmd(args)
