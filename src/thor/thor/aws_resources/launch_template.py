from thor.aws_resources.aws_resource import AwsResource


class LaunchTemplateException(Exception):
    pass


class LaunchTemplate(AwsResource):

    def __init__(self, env):
        super().__init__('ec2', env, 'launch_template')

    def __parse_params(self, **params):
        parsed_params = {}

        if 'name' in params:
            parsed_params['LaunchTemplateName'] = params['name']
        if 'launch_template_data' in params:
            parsed_params['LaunchTemplateData'] = params['launch_template_data']
        if 'version' in params:
            parsed_params['Versions'] = [params['version']]

        return parsed_params

    def create(self, name, launch_template_data):
        saved_params = locals()
        try:
            output_status('Creating {}...'.format(name))
            response = self.client().create_launch_template(
                self.__parse_params(saved_params)
            )
            if 'LaunchTemplate' in response:
                return response['LaunchTemplate']['LaunchTemplateName']
            output_status('Created')
        except Exception as err:
            raise LaunchTemplateException(str(err))

    def destroy(self, name):
        saved_params = locals()
        try:
            output_status('Deleting {}...'.format(name))
            ec2.delete_launch_template(
                self.__parse_params(saved_params)
            )
            output_status('Deleted')
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
                self.__parse_params(saved_params)
            )
            if 'LaunchTemplateVersions' in response:
                return response['LaunchTemplateVersions'][0]
            else:
                return None
        except Exception as err:
            raise LaunchTemplateException(str(err))

    def update(self, Name):
        pass