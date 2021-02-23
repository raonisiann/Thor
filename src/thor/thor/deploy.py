#!/usr/bin/env python3

import argparse
import datetime
import time
from .env import Env
from .image import Image
from .param import Param


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


class Deploy:

    def __init__(self, image):
        self.image = image
        self.deploy_strategy = 'blue_green'
        self.current_state = {}
        self.created_resources = []

    def attach_auto_scaling_group_to_target_group(self):
        pass

    def dettach_auto_scaling_group_from_target_group(self):
        pass

    def create_auto_scaling_group(self, asg_data):
        asg_client = self.image.env.aws_client('autoscaling')

        try:
            print('Creating Auto Scaling group {}...'.format(
                asg_data['AutoScalingGroupName']
            ))
            asg_client.create_auto_scaling_group(
                **asg_data
            )
            self.created_resources.append({
                'name': 'auto_scaling_group',
                'data': asg_data['AutoScalingGroupName']
            })
            print('Auto Scaling group created.')
        except Exception as err:
            raise DeployException(str(err))

    def create_launch_template(self, name, launch_template_data):
        ec2 = self.image.env.aws_client('ec2')

        try:
            print('Creating Launch Template {}...'.format(
                name
            ))
            response = ec2.create_launch_template(
                LaunchTemplateName=name,
                LaunchTemplateData=launch_template_data
            )

            if 'LaunchTemplate' in response:
                self.created_resources.append({
                    'name': 'launch_template',
                    'data': response['LaunchTemplate']['LaunchTemplateName']
                })
                return response['LaunchTemplate']['LaunchTemplateName']
            print('Launch Template created')
        except Exception as err:
            raise DeployException(str(err))

    def delete_launch_template(self, name):
        ec2 = self.image.env.aws_client('ec2')

        try:
            print('Deleting Launch Template {}...'.format(name))
            ec2.delete_launch_template(
                LaunchTemplateName=name
            )
            print('Launch Template deleted')
        except ec2.exceptions.ResourceInUseFault:
            raise DeployException('Fail to delete launch template.'
                                  'Resource in use')
        except ec2.exceptions.ResourceContentionFault as err:
            raise DeployException(str(err))

    def do_blue_green_deploy_abort(self):
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

    def get_auto_scaling_group_by_name(self, asg_name):
        asg_client = self.image.env.aws_client('autoscaling')

        try:
            response = asg_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[asg_name]
            )

            if 'AutoScalingGroups' not in response:
                raise DeployException('No AutoScaling groups were found')

            if len(response['AutoScalingGroups']) == 1:
                return response['AutoScalingGroups'][0]
            return response['AutoScalingGroups']
        except Exception as err:
            raise DeployException(str(err))

    def get_launch_template_by_name(self, launch_template_name):
        ec2 = self.image.env.aws_client('ec2')

        try:
            response = ec2.describe_launch_template_versions(
                LaunchTemplateName=launch_template_name,
                Versions=[
                    '$Latest'
                ]
            )

            if 'LaunchTemplateVersions' not in response:
                raise DeployException('No Launch templates were found')

            return response['LaunchTemplateVersions'][0]
        except Exception as err:
            raise DeployException(str(err))

    def terminate_auto_scaling_group(self, name):
        print('Terminating Auto Scaling group {}...'.format(name))

        asg = self.get_auto_scaling_group_by_name(name)
        seconds_between_termination_requests = 5
        interval_check_seconds = 30
        target_capacity = 0
        current_capacity = asg['DesiredCapacity']
        asg_client = self.image.env.aws_client('autoscaling')

        print('Setting ASG minSize to 0...')
        asg_client.update_auto_scaling_group(
            AutoScalingGroupName=name,
            MinSize=0
        )
        print('ASG minSize=0 done.')

        while current_capacity != target_capacity:
            non_terminated = 0
            for i in asg['Instances']:
                # send terminate request to all 'InService' instances
                if i['LifecycleState'] == 'InService':
                    try:
                        asg_client.terminate_instance_in_auto_scaling_group(
                            InstanceId=i['InstanceId'],
                            ShouldDecrementDesiredCapacity=True
                        )
                        print('Auto Scaling group instance '
                              'termination request sent.')
                    except Exception as err:
                        raise DeployException(str(err))
                    print('Waiting {} seconds before send '
                          'another termination request.'.format(
                                seconds_between_termination_requests
                          ))
                    time.sleep(seconds_between_termination_requests)
                if i['LifecycleState'] != 'Terminated':
                    non_terminated += 1

            asg = self.get_auto_scaling_group_by_name(name)
            current_capacity = asg['DesiredCapacity']

            print('Capacity {} --> {}'.format(
                current_capacity,
                target_capacity
            ))
            # collect instance status summary
            instance_status_summary = {}

            for i in asg['Instances']:
                state = i['LifecycleState']
                if state in instance_status_summary:
                    instance_status_summary[state] += 1
                else:
                    instance_status_summary[state] = 1

            print('Instance Summary:')
            for status, count in instance_status_summary.items():
                print('  {} = {}'.format(count, status))

            print('Waiting {} seconds before next check...'.format(
                interval_check_seconds
            ))
            time.sleep(interval_check_seconds)

        print('Auto scaling instances terminated')

        scale_event_in_progress = True

        while scale_event_in_progress:
            try:
                print('Deleting auto scaling group {}'.format(name))
                asg_client.delete_auto_scaling_group(
                    AutoScalingGroupName=name
                )
                print('Auto scaling group deleted.')
                scale_event_in_progress = False
            except asg_client.exceptions.ScalingActivityInProgressFault:
                print('Auto scaling group activity in progress. '
                      'Waiting 30 seconds for next attempt...')
                time.sleep(30)
            except Exception as err:
                print('Fail to delete auto scaling group with error:')
                print(str(err))
                scale_event_in_progress = False

    def wait_for_desired_capacity(self, asg_name, desired_capacity,
                                  wait_seconds=1):
        # set initial capacity
        current_capacity = 0
        print('Waiting instances to become available...')

        while desired_capacity != current_capacity:
            print('Waiting {} seconds to perform new check'.format(
                wait_seconds
            ))
            time.sleep(wait_seconds)
            asg = self.get_auto_scaling_group_by_name(asg_name)
            count_capacity = 0

            if 'Instances' in asg:
                for instance in asg['Instances']:
                    if not instance['HealthStatus'] == 'Healthy':
                        continue
                    if not instance['LifecycleState'] == 'InService':
                        continue
                    count_capacity += 1

            current_capacity = count_capacity
            print('Current capacity = {}'.format(current_capacity))
            print('Desired capacity = {}'.format(desired_capacity))


def deploy_cmd(args):
    print('Deploying...')

    img = Image(env=args.env, name=args.image)
    ps = Param(args.env)

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
