import botocore
import time
from thor.lib.aws_resources.aws_resource import AwsResource


class AutoScalingException(Exception):
    pass


class AutoScalingActivityInProgress(Exception):
    pass


class AutoScaling(AwsResource):

    def __init__(self, env):
        super().__init__('autoscaling', env)

    def __parse_params(self, params):
        params = self.sanitize_dict(params)
        parsed_config = {}

        if 'name' in params:
            parsed_config['AutoScalingGroupName'] = params['name']

        if 'names' in params:
            name_list = [params['names']]
            parsed_config['AutoScalingGroupNames'] = name_list

        if 'launch_template_name' in params:
            lt_name = params['launch_template_name']
            parsed_config['LaunchTemplate'] = {}
            parsed_config['LaunchTemplate']['LaunchTemplateName'] = lt_name

        if 'min_capacity' in params:
            parsed_config['MinSize'] = params['min_capacity']

        if 'max_capacity' in params:
            parsed_config['MaxSize'] = params['max_capacity']

        if 'desired_capacity' in params:
            parsed_config['DesiredCapacity'] = params['desired_capacity']

        if 'defaul_cooldown' in params:
            parsed_config['DefaultCooldown'] = params['default_cooldown']

        if 'availability_zones' in params:
            parsed_config['AvailabilityZones'] = params['availability_zones']

        if 'target_group_arn' in params:
            parsed_config['TargetGroupARNs'] = [params['target_group_arn']]

        if 'health_check_type' in params:
            parsed_config['HealthCheckType'] = params['health_check_type']

        if 'health_check_grace_period' in params:
            hc_period = params['health_check_grace_period']
            parsed_config['HealthCheckGracePeriod'] = hc_period

        if 'vpc_zone_identifier' in params:
            vpc_subnets = ','.join(params['vpc_zone_identifier'])
            parsed_config['VPCZoneIdentifier'] = vpc_subnets

        if 'tags' in params and params['tags']:
            parsed_config['Tags'] = params['tags']

        return parsed_config

    def __is_instance_health(self, instance):
        health_status = instance['HealthStatus']
        lifecycle_status = instance['LifecycleState']
        # only considered healthy if both states matches
        if health_status == 'Healthy' and lifecycle_status == 'InService':
            return True
        else:
            return False

    def __check_instance_ready_state(self, name, desired_capacity):
        asg = self.read(name)
        current_capacity = 0

        if 'Instances' in asg:
            for instance in asg['Instances']:
                if self.__is_instance_health(instance):
                    current_capacity += 1
        self.logger.info('Current capacity = {}'.format(current_capacity))
        self.logger.info('Desired capacity = {}'.format(desired_capacity))

        if desired_capacity == current_capacity:
            return True

    def __terminate_autoscaling_instance(self, instance_id):
        try:
            self.client().terminate_instance_in_auto_scaling_group(
                InstanceId=instance_id,
                ShouldDecrementDesiredCapacity=True
            )
            self.logger.info('Termination request sent for %s', instance_id)
        except self.client().exceptions.ScalingActivityInProgressFault as err:
            raise AutoScalingException(str(err))
        except self.client().exceptions.ResourceContentionFault as err:
            raise AutoScalingException(str(err))

    def __wait_for_instances_terminated_state(self, name):
        seconds_between_termination_requests = 2
        interval_check_seconds = 30
        target_capacity = 0

        while True:
            asg = self.read(name)
            state_summary = {}
            instance_count = len(asg['Instances'])

            for i in asg['Instances']:
                state = i['LifecycleState']
                # summarize instance status
                if state in state_summary:
                    state_summary[state] += 1
                else:
                    state_summary[state] = 1

                if state == 'InService':
                    # send terminate request to all 'InService' instances
                    self.__terminate_autoscaling_instance(i['InstanceId'])
                    time.sleep(seconds_between_termination_requests)

            self.logger.info('Capacity {} -> {}'.format(instance_count,
                                                        target_capacity))

            if instance_count:
                self.logger.info('Instance state summary')
                for status, count in state_summary.items():
                    self.logger.info('  {} = {}'.format(count, status))
            else:
                # no instances left on autoscaling...
                break
            self.logger.info('Waiting %s seconds...', interval_check_seconds)
            time.sleep(interval_check_seconds)
        self.logger.info('Instances terminated')

    def create(self, name, launch_template_name, min_capacity,
               max_capacity, desired_capacity, default_cooldown=None,
               availability_zones=None, target_group_arn=None,
               health_check_type=None, health_check_grace_period=None,
               vpc_zone_identifier=None, tags=None):
        saved_params = locals()
        try:
            parsed_config = self.__parse_params(saved_params)
            self.logger.info('Creating {}...'.format(name))

            for k, v in parsed_config.items():
                self.logger.info('{}={}'.format(k, v))
            response = self.client().create_auto_scaling_group(
                **parsed_config
            )
            # wait for autoscaling and instance lifecycle completes
            self.logger.info('Waiting instances to become available...')
            self.wait_for(15, 1200, self.__check_instance_ready_state, name,
                          desired_capacity)
            self.logger.info('Instances available.')
            self.logger.info('Created')
        except botocore.exceptions.ParamValidationError as err:
            raise AutoScalingException(str(err))
        except botocore.exceptions.ClientError as err:
            raise AutoScalingException(str(err))
        except self.client().exceptions.AlreadyExistsFault as err:
            raise AutoScalingException(str(err))
        except self.client().exceptions.LimitExceededFault as err:
            raise AutoScalingException(str(err))
        except self.client().exceptions.ResourceContentionFault as err:
            raise AutoScalingException(str(err))
        except self.client().exceptions.ServiceLinkedRoleFailure as err:
            raise AutoScalingException(str(err))

    def destroy(self, name):
        saved_params = locals()
        seconds_to_wait_for_autoscaling_activity = 30
        self.logger.info('Terminating {}...'.format(name))

        try:
            self.update(name, min_capacity=0)
        except AutoScalingActivityInProgress:
            raise AutoScalingException('Can\'t proceed with destroy.'
                                       'AutoScaling activity in progress.')

        self.__wait_for_instances_terminated_state(name)
        scale_event_in_progress = True

        while scale_event_in_progress:
            try:
                self.logger.info('Destroying {}...'.format(name))
                self.client().delete_auto_scaling_group(
                    **self.__parse_params(saved_params)
                )
                scale_event_in_progress = False
            except self.client().exceptions.ScalingActivityInProgressFault:
                self.logger.info('Activity in progress. Can\'t delete.')
                self.logger.info('Waiting %s seconds for next attempt...',
                                 seconds_to_wait_for_autoscaling_activity)
                time.sleep(seconds_to_wait_for_autoscaling_activity)
            except self.client().exceptions.ResourceContentionFault as err:
                raise AutoScalingException(str(err))
            except self.client().exceptions.ResourceInUseFault as err:
                raise AutoScalingException(str(err))
        self.logger.info('{} destroyed.'.format(name))

    def discover(self, name):
        try:
            filters = [
                {
                    'Name': 'key',
                    'Values': ['Name']
                },
                {
                    'Name': 'value',
                    'Values': [name]
                }
            ]
            return self.tokenized(self.client().describe_tags,
                                  'Tags', Filters=filters)
        except self.client().exceptions.InvalidNextToken as err:
            raise AutoScalingException(str(err))
        except self.client().exceptions.ResourceContentionFault as err:
            raise AutoScalingException(str(err))

    def read(self, names):
        saved_params = locals()
        try:
            response = self.client().describe_auto_scaling_groups(
                **self.__parse_params(saved_params)
            )

            if 'AutoScalingGroups' not in response:
                raise AutoScalingException('No AutoScaling groups were found')

            return response['AutoScalingGroups'][0]
        except self.client().exceptions.InvalidNextToken as err:
            raise AutoScalingException(str(err))
        except self.client().exceptions.ResourceContentionFault as err:
            raise AutoScalingException(str(err))

    def update(self, name, launch_template_name=None, min_capacity=None,
               max_capacity=None, desired_capacity=None, default_cooldown=None,
               availability_zones=None, health_check_type=None,
               health_check_grace_period=None, vpc_zone_identifier=None):
        saved_params = locals()
        try:
            parsed_params = self.__parse_params(saved_params)
            self.logger.info('Updating {}...'.format(name))
            for k, v in parsed_params.items():
                self.logger.info('setting: {} = {}'.format(k, v))

            response = self.client().update_auto_scaling_group(
                **parsed_params
            )
            self.logger.info('{} updated.'.format(name))
        except self.client().exceptions.ScalingActivityInProgressFault as err:
            raise AutoScalingActivityInProgress(str(err))
        except self.client().exceptions.ResourceContentionFault as err:
            raise AutoScalingException(str(err))
        except self.client().exceptions.ServiceLinkedRoleFailure as err:
            raise AutoScalingException(str(err))
