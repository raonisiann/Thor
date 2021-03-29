from thor.lib.aws_resources.aws_resource import AwsResource


class LaunchTemplateException(Exception):
    pass


class LaunchTemplate(AwsResource):

    def __init__(self, env):
        super().__init__('ec2', env, 'launch_template')

    def create(self, name, data):
        try:
            self.logger.info('Creating {}...'.format(name))
            data = self.translate_dict_to_aws_config_names(data)
            for k, v in data.items():
                self.logger.info('{}={}'.format(k, v))
            response = self.client().create_launch_template(
                LaunchTemplateName=name,
                VersionDescription='Create by thor',
                LaunchTemplateData=data
            )
            if 'LaunchTemplate' in response:
                self.logger.info('Created')
                return response['LaunchTemplate']['LaunchTemplateName']
        except Exception as err:
            raise LaunchTemplateException(str(err))

    def destroy(self, name):
        try:
            self.logger.info('Deleting {}...'.format(name))
            self.client().delete_launch_template(
                LaunchTemplateName=name
            )
            self.logger.info('Deleted')
        except self.client().exceptions.ResourceInUseFault:
            raise LaunchTemplateException('Resource in use')
        except self.client().exceptions.ResourceContentionFault as err:
            raise LaunchTemplateException(str(err))

    def discover(self, name):
        pass

    def read(self, name, version='$Latest'):
        try:
            response = self.client().describe_launch_template_versions(
                LaunchTemplateName=name,
                Versions=[version]
            )
            if 'LaunchTemplateVersions' in response:
                return response['LaunchTemplateVersions'][0]
            else:
                return None
        except Exception as err:
            raise LaunchTemplateException(str(err))

    def update(self, Name):
        pass
