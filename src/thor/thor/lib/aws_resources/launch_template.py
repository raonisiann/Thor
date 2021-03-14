from thor.lib.aws_resources.aws_resource import AwsResource


class LaunchTemplateException(Exception):
    pass


class LaunchTemplate(AwsResource):

    def __init__(self, env):
        super().__init__('ec2', env, 'launch_template')

    def __parse_params(self, params):
        parsed_params = {}
        parsed_params['LaunchTemplateData'] = {}
        if 'name' in params:
            parsed_params['LaunchTemplateName'] = params['name']
        if 'image_id' in params:
            parsed_params['LaunchTemplateData']['ImageId'] = params['image_id']
        if 'instance_type' in params:
            parsed_params['LaunchTemplateData']['InstanceType'] = params['instance_type']
        if 'key_pair' in params and params['key_pair'] is not None:
            parsed_params['LaunchTemplateData']['KeyName'] = params['key_pair']
        if 'version' in params:
            parsed_params['Versions'] = [params['version']]

        if not parsed_params['LaunchTemplateData']:
            del(parsed_params['LaunchTemplateData'])
        return parsed_params

    def create(self, name, image_id, instance_type, key_pair=None):
        saved_params = locals()
        try:
            parsed_params = self.__parse_params(saved_params)
            self.logger.info('Creating {}...'.format(name))
            for k, v in parsed_params.items():
                self.logger.info('{}={}'.format(k, v))
            response = self.client().create_launch_template(
                **parsed_params
            )
            if 'LaunchTemplate' in response:
                return response['LaunchTemplate']['LaunchTemplateName']
            self.logger.info('Created')
        except Exception as err:
            raise LaunchTemplateException(str(err))

    def destroy(self, name):
        saved_params = locals()
        try:
            self.logger.info('Deleting {}...'.format(name))
            ec2.delete_launch_template(
                **self.__parse_params(saved_params)
            )
            self.logger.info('Deleted')
        except self.client().exceptions.ResourceInUseFault:
            raise LaunchTemplateException('Resource in use')
        except self.client().exceptions.ResourceContentionFault as err:
            raise LaunchTemplateException(str(err))

    def discover(self, name):
        pass

    def read(self, name, version='$Latest'):
        saved_params = locals()
        try:
            response = self.client().describe_launch_template_versions(
                **self.__parse_params(saved_params)
            )
            if 'LaunchTemplateVersions' in response:
                return response['LaunchTemplateVersions'][0]
            else:
                return None
        except Exception as err:
            raise LaunchTemplateException(str(err))

    def update(self, Name):
        pass