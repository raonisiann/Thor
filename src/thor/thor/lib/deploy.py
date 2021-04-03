import abc
import time
from datetime import datetime
from thor.lib.base import Base
from thor.lib.aws_resources.autoscaling import (
    AutoScaling,
    AutoScalingException
)
from thor.lib.aws_resources.launch_template import (
    LaunchTemplate,
    LaunchTemplateException
)
from thor.lib.utils.names_generator import random_string


class DeployException(Exception):
    pass


class DeployLockException(Exception):
    pass


class DeployLockAlreadyAcquiredException(Exception):
    pass


class Deploy(Base):

    __metaclass__ = abc.ABCMeta

    DEFAULT_DESIRED_CAPACITY = 1

    def __init__(self, image):
        super().__init__()
        self.image = image
        self.autoscaling_config = DeployAutoScalingConfig(image)
        self.created_resources = {}
        self.running_resources = {}

    @abc.abstractmethod
    def abort(self):
        return

    @abc.abstractmethod
    def run(self):
        return


class DeployLock(Base):

    LOCK_TEMPLATE = 'owner={owner},timestamp={timestamp}'

    def __init__(self, image):
        super().__init__()
        self.image = image
        self.lock = ''

    def __generate_lock_info(self):
        timestamp = int(datetime.now().timestamp())
        owner = 'unknown'
        return DeployLock.LOCK_TEMPLATE.format(
            owner=owner,
            timestamp=timestamp
        )

    def acquire(self):
        self.logger.info('Acquiring...')
        self.lock = self.__generate_lock_info()

        if self.image.params.deploy_lock is not None:
            raise DeployLockAlreadyAcquiredException()
        self.image.params.deploy_lock = self.lock
        return self

    def release_force(self):
        del(self.image.params.deploy_lock)

    def release(self):
        self.logger.info('Releasing...')
        if self.lock:
            self.release_force()
            self.lock = ''

    def __enter__(self):
        return self.acquire()

    def __exit__(self, type, value, traceback):
        self.release()


class DeployAutoScalingConfig:

    def __init__(self, image):
        self.__autoscaling_settings = image.config().get('scaling')

    def __getattr__(self, name):
        if name in self.__autoscaling_settings:
            return self.__autoscaling_settings[name]
        else:
            raise AttributeError('Unknown autoscaling setting %s', name)


class DeployBlueGreen(Deploy):

    def __init__(self, image):
        super().__init__(image)
        self.ami_id = ''
        self.autoscaling = AutoScaling(image.env)
        self.is_first_deploy_ever = False
        self.launch_template = LaunchTemplate(image.env)

    def settle_down(self, seconds=30):
        self.logger.info('Settle down for %s seconds', seconds)
        time.sleep(30)

    def abort(self):
        self.logger.info('Aborting...')
        exit(-1)

    def pre_init_step(self):
        self.logger.info('Pre init step started...')
        self.ami_id = self.image.get_latest_ami_id()
        running_autoscaling = self.image.params.autoscaling_name

        if not self.ami_id:
            raise DeployException('Could not get latest AMI.'
                                  'You may need to build the '
                                  'image before deploy it.')
        self.logger.info('AMI_ID = %s', self.ami_id)

        if not running_autoscaling:
            self.logger.info('No running autoscaling groups were found.')
            self.is_first_deploy_ever = True
        else:
            try:
                asg_data = self.autoscaling.read(running_autoscaling)
                self.logger.info('Found running autoscaling %s',
                                 asg_data['AutoScalingGroupName'])
                self.logger.info('%s Current Capacity = %s',
                                 asg_data['AutoScalingGroupName'],
                                 asg_data['DesiredCapacity'])
                self.running_resources['autoscaling'] = asg_data

                if 'LaunchTemplate' in asg_data:
                    lt_name = asg_data['LaunchTemplate']['LaunchTemplateName']
                    self.running_resources['launch_template'] = lt_name
            except AutoScalingException:
                self.logger.warning(
                    'Unable to read AutoScaling {}. '
                    'The auto scaling no longer exists or '
                    'you dont have permissions to read it.'.format(
                        running_autoscaling))
                self.do_blue_green_rollback()
                self.abort()

        self.logger.info('Pre init step completed.')

    def create_launch_template_from_config(self):
        # create new launch configuration
        name = 'LT_{image}_{env}_{rand}'.format(
            image=self.image.get_name(),
            env=self.image.env.get_name(),
            rand=random_string()
        )
        config = self.image.config().get('launch_template')
        if config is None:
            raise DeployException('launch_template is not defined '
                                  'in config file')

        if 'instance_type' not in config:
            raise DeployException('instance_type not defined in config file')

        config['image_id'] = self.ami_id

        try:
            self.launch_template.create(name, config)
        except LaunchTemplateException as err:
            raise DeployException(str(err))

        self.created_resources['launch_template'] = name
        return name

    def create_autoscaling(self, launch_template_name):
        new_autoscaling_name = 'ASG_{image}_{env}_{rand}'.format(
            image=self.image.get_name(),
            env=self.image.env.get_name(),
            rand=random_string()
        )

        if self.is_first_deploy_ever:
            desired_capacity = Deploy.DEFAULT_DESIRED_CAPACITY
        else:
            current_autoscaling = self.running_resources['autoscaling']
            try:
                desired_capacity = current_autoscaling['DesiredCapacity']
            except KeyError:
                raise DeployException('Cannot find desired capacity '
                                      'for running auto scaling.')

        autoscaling_config = self.image.config().get('scaling')
        autoscaling_config['desired_capacity'] = desired_capacity

        try:
            self.autoscaling.create(new_autoscaling_name,
                                    launch_template_name, autoscaling_config)
            self.created_resources['autoscaling'] = new_autoscaling_name
        except AutoScalingException as err:
            raise DeployException(str(err))
        return new_autoscaling_name

    def create_green_environment_step(self):
        launch_template_name = self.create_launch_template_from_config()
        autoscaling_name = self.create_autoscaling(launch_template_name)
        return autoscaling_name

    def terminate_blue_environment_step(self):
        self.logger.info('Terminating blue environment...')

        if 'autoscaling' in self.running_resources:
            running_autoscaling = self.running_resources['autoscaling']
            try:
                self.autoscaling.destroy(
                 running_autoscaling['AutoScalingGroupName'])
            except AutoScalingException as err:
                raise DeployException(str(err))

        if 'launch_template' in self.running_resources:
            running_launch_template = self.running_resources['launch_template']
            try:
                self.launch_template.destroy(running_launch_template)
            except LaunchTemplateException:
                # this is not an issue, will just keep trash
                # launch templates on the aws account.
                self.logger.warning('Could not delete launch template')

    def run(self):
        try:
            with DeployLock(self.image):
                self.pre_init_step()
                green_autoscaling = self.create_green_environment_step()
                self.settle_down(20)

                if not self.is_first_deploy_ever:
                    self.terminate_blue_environment_step()

                self.image.params.autoscaling_name = green_autoscaling
                return 'success'
        except KeyboardInterrupt:
            self.logger.info('Deploy CANCELLED by user')
            self.do_blue_green_rollback()
            return 'cancelled'
        except DeployLockAlreadyAcquiredException:
            self.logger.error('Lock already acquired. Can\'t proceed...')
            exit(-1)
            return 'fail'
        except DeployException as err:
            self.logger.error(str(err))
            self.do_blue_green_rollback()
            return 'fail'

    def do_blue_green_rollback(self):
        self.logger.info('Running rollback actions...')

        if 'autoscaling' in self.created_resources:
            self.autoscaling.destroy(self.created_resources['name'])
        if 'launch_template' in self.created_resources:
            self.launch_template.destroy(
                self.created_resources['launch_template'])
