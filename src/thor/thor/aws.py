import boto3
import botocore
from botocore.config import Config


class AwsClientException(Exception):
    pass


class Aws:

    def __init__(self, region, profile=None):
        self.region = region
        self.profile = profile

    def client(self, service):
        my_config = Config(
            signature_version='v4',
            retries={
                'max_attempts': 10,
                'mode': 'standard'
            }
        )

        try:
            session = boto3.Session(
                profile_name=self.profile
            )
        except botocore.exceptions.ProfileNotFound:
            # fallback to default settings
            print('No profile found. Fallback to default credential chain...')
            session = boto3.Session()

        try:
            client = session.client(
                service,
                config=my_config,
                region_name=self.region
            )
            return client
        except Exception as err:
            raise AwsClientException(
                'Fail to get AWS Client with error: {}'.format(
                    str(err)
                )
            )
