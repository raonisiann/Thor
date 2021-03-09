from thor.aws_resources.aws_resource import AwsResource


class AutoScalingException(Exception):
    pass


class AutoScalingActivityInProgress(Exception):
    pass


class AutoScaling(AwsResource):

    def __init__(self, env):
        super().__init__('autoscaling', env)

    def __parse_params(self, **params):
        parsed_config = {}

        if 'name' in params:
            parsed_config['AutoScalingGroupName'] = params['name']

        if 'names' in params:
            parsed_config['AutoScalingGroupNames'] = params['names']

        if 'launch_template_name' in params:
            parsed_config['LaunchTemplate'] = {}
            parsed_config['LaunchTemplate']['LaunchTemplateName'] = params['launch_template_name']

        if 'min_size' in params:
            parsed_config['MinSize'] = params['min_size']

        if 'max_size' in params:
            parsed_config['MaxSize'] = params['max_size']

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
            parsed_config['HealthCheckGracePeriod'] = params['health_check_grace_period']

        if 'vpc_zone_identifier' in params:
            parsed_config['VPCZoneIdentifier'] = params['vpc_zone_identifier']

        if 'tags' in params:
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
        output_status('Current capacity = {}'.format(current_capacity))
        output_status('Desired capacity = {}'.format(desired_capacity))

        if desired_capacity == current_capacity:
            return True

    def __terminate_autoscaling_instance(self, instance_id):
        try:
            asg_client.terminate_instance_in_auto_scaling_group(
                InstanceId=instance_id,
                ShouldDecrementDesiredCapacity=True
            )
            output_status('Termination request sent for {}'.format(instance_id))
        except self.client().exceptions.ScalingActivityInProgressFault as err:
            raise DeployException(str(err))
        except self.client().exceptions.ResourceContentionFault as err:
            raise DeployException(str(err))

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

            output_status('Capacity {} -> {}'.format(instance_count, target_capacity))

            if instance_count:
                output_status('Instance state summary')
                for status, count in instance_status_summary.items():
                    output_status('  {} = {}'.format(count, status))
            else:
                # no instances left on autoscaling...
                break
            output_status('Waiting {} seconds...'.format(interval_check_seconds))
            time.sleep(interval_check_seconds)
        output_status('Instances terminated')

    def create(self, name, launch_template_name, min_size,
               max_size, desired_capacity, default_cooldown=None,
               availability_zones=None, target_group_arn=None, health_check_type=None,
               health_check_grace_period=None, vpc_zone_identifier=None, tags=None):
        saved_params = locals()
        try:
            output_status('Creating {}...'.format(name))
            response = self.client().create_auto_scaling_group(
                self.__parse_params(**saved_params)
            )
            # wait for autoscaling and instance lifecycle completes
            output_status('Waiting instances to become available...')
            self.wait_for(5, 1200, self.__check_instance_ready_state, name, desired_capacity)
            output_status('Instances available.')
            output_status('Created')
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
        output_status('Terminating {}...'.format(name))

        try:
            self.update(name, min_size=0)
        except AutoScalingActivityInProgress:
            raise AutoScalingException('Can\'t proceed with destroy. AutoScaling activity in progress.')

        self.__wait_for_instances_terminated_state(name)
        scale_event_in_progress = True

        while scale_event_in_progress:
            try:
                output_status('Destroying {}...'.format(name))
                self.client().delete_auto_scaling_group(
                    self.__parse_params(**saved_params)
                )
                scale_event_in_progress = False
            except self.client().exceptions.ScalingActivityInProgressFault:
                output_status('Activity in progress. Can\'t delete.')
                output_status('Waiting {} seconds for next attempt...'.format(
                    seconds_to_wait_for_autoscaling_activity
                ))
                time.sleep(seconds_to_wait_for_autoscaling_activity)
            except self.client().exceptions.ResourceContentionFault as err:
                raise AutoScalingException(str(err))
            except self.client().exceptions.ResourceInUseFault as err:
                raise AutoScalingException(str(err))
        output_status('{} destroyed.'.format(name))

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
                self.__parse_params(**saved_params)
            )

            if 'AutoScalingGroups' not in response:
                raise AutoScalingException('No AutoScaling groups were found')

            return response['AutoScalingGroups'][0]
        except self.client().exceptions.InvalidNextToken as err:
            raise AutoScalingException(str(err))
        except self.client().exceptions.ResourceContentionFault as err:
            raise AutoScalingException(str(err))

    def update(self, name, launch_template_name=None, min_size=None,
               max_size=None, desired_capacity=None, default_cooldown=None,
               availability_zones=None, health_check_type=None,
               health_check_grace_period=None, vpc_zone_identifier=None):
        saved_params = locals()
        try:
            output_status('Updating {}...'.format(name))
            for k, v in config:
                output_status('setting: {} = {}'.format(k, v))

            response = self.client().update_auto_scaling_group(
                self.__parse_params(**saved_params)
            )
            output_status('{} updated.'.format(name))
        except self.client().exceptions.ScalingActivityInProgressFault as err:
            raise AutoScalingActivityInProgress(str(err))
        except self.client().exceptions.ResourceContentionFault as err:
            raise AutoScalingException(str(err))
        except self.client().exceptions.ServiceLinkedRoleFailure as err:
            raise AutoScalingException(str(err))
