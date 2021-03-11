import time
from thor.lib.env import Env
from thor.lib.aws_resources.aws_resource import (
    AwsResource,
    AwsResourceTimeoutException,
    AwsResourceParameterException
)
from unittest import TestCase


def fake_api_call(sleep_for=1, exit_status=True):
    time.sleep(sleep_for)
    return exit_status


class TestAwsResource(TestCase):

    def setUp(self):
        self.env = Env('test')

    def test_wait_for_normal_exit(self):
        aws_resource = AwsResource('testresource', self.env)
        self.assertTrue(
            aws_resource.wait_for(retry_interval=1, timeout=2, func=fake_api_call)
        )

    def test_wait_for_timed_out(self):
        aws_resource = AwsResource('testresource', self.env)
        with self.assertRaises(AwsResourceTimeoutException):
            aws_resource.wait_for(retry_interval=1, timeout=1, func=fake_api_call, exit_status=False)

    def test_wait_for_invalid_parameters(self):
        aws_resource = AwsResource('testresource', self.env)
        with self.assertRaises(AwsResourceParameterException):
            aws_resource.wait_for(retry_interval=1, timeout=0, func=fake_api_call)
        with self.assertRaises(AwsResourceParameterException):
            aws_resource.wait_for(retry_interval=0, timeout=1, func=fake_api_call)