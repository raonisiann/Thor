import boto3
import sys


class AwsAmiFinderException(Exception):
    pass


class AwsAmiFinder:
    #
    # Default parameters for AMI Filter
    #
    # Avoid editing them by hand. They can be
    # overriden (most) on command line
    #

    # For Amazon Linux: amzn-ami-hvm-*
    # For Ubuntu: *ubuntu-focal-20.04-amd64-server*
    IMAGE_FILTER_NAME = '*ubuntu-focal-20.04-amd64-server*'
    IMAGE_FILTER_ARCHITECTURE = 'x86_64'
    IMAGE_FILTER_STATE = 'available'
    IMAGE_FILTER_ROOT_DEVICE_TYPE = 'ebs'
    IMAGE_FILTER_VIRTUALIZATION_TYPE = 'hvm'
    IMAGE_FILTER_HYPERVISOR = 'xen'
    IMAGE_FILTER_TYPE = 'machine'
    IMAGE_FILTER_IS_PUBLIC = 'True'

    AMI_DEFAULT_FILTER = {
        'architecture': IMAGE_FILTER_ARCHITECTURE,
        'image-type': IMAGE_FILTER_TYPE,
        'hypervisor': IMAGE_FILTER_HYPERVISOR,
        'name': IMAGE_FILTER_NAME,
        'root-device-type': IMAGE_FILTER_ROOT_DEVICE_TYPE,
        'state': IMAGE_FILTER_STATE,
        'virtualization-type': IMAGE_FILTER_VIRTUALIZATION_TYPE,
    }

    def __init__(self, region):
        self.region = region
        self.__images = []

    def __parser_filters(self, str_filters):
        input_filter_dict = {}

        if str_filters:
            for f in str_filters.split(','):
                try:
                    k, v = f.split('=')
                    # ignore unknown filters...
                    if k not in AwsAmiFinder.AMI_DEFAULT_FILTER:
                        continue
                    input_filter_dict[k] = v
                except Exception as ex:
                    print('Something wrong with filter {}'.format(f))
                    print(str(ex))
        return {**AwsAmiFinder.AMI_DEFAULT_FILTER, **input_filter_dict}

    def build_aws_ami_filters(self, input_filters):
        parsed_filters = self.__parser_filters(input_filters)
        aws_ami_filter = []

        for name, value in parsed_filters.items():
            aws_ami_filter.append({
                'Name': name,
                'Values': [value, ]
            })
        return aws_ami_filter

    def __is_valid_filter_key(self, key):
        for f in AwsAmiFinder.AMI_DEFAULT_FILTER:
            if key == f['Name']:
                return True
        return False

    def __remove_marketplace_amis(self, images):
        cleaned_amis = []

        for image in images:
            if 'aws-marketplace' in image['ImageLocation']:
                continue
            cleaned_amis.append(image)
        return cleaned_amis

    def get_latest_image(self, filters):
        image_list = self.get_images(filters)
        image_list = self.__remove_marketplace_amis(image_list)

        if image_list:
            latest_ami = sorted(
                image_list,
                key=lambda x: x['CreationDate'],
                reverse=True
            )
            return latest_ami[0]

    def get_images(self, filters):
        client = boto3.client(
            'ec2',
            region_name=self.region
        )

        try:
            response = client.describe_images(
                Filters=self.build_aws_ami_filters(filters)
            )
            return response['Images']
        except Exception as err:
            print('Something went wrong while getting the AMI list from AWS.')
            print(str(err), file=sys.stderr)
            exit(-1)

    def get_image(self, id):

        try:
            ec2 = boto3.resource('ec2')
            image = ec2.Image(id)
            return image
        except Exception as err:
            print(
                'Something went wrong while getting image from AWS.',
                file=sys.stderr
            )
            print(str(err), file=sys.stderr)
