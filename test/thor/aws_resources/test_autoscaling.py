from unittest import TestCase
from thor.aws_resources.autoscaling import AutoScaling
from thor.env import Env

class TestAutoScalingGroup(TestCase):

    def setUp(self):
        self.env = Env('test')

    def test_parse_params_only_name(self):
        autoscaling = AutoScaling(self.env)
        result = autoscaling._AutoScaling__parse_params(name='test')
        self.assertDictEqual(result, {'AutoScalingGroupName': 'test'})

    def test_is_instance_healthy_true(self):
        autoscaling = AutoScaling(self.env)
        fake_health_input = {
            'HealthStatus': 'Healthy',
            'LifecycleState': 'InService'
        }
        self.assertTrue(autoscaling._AutoScaling__is_instance_health(fake_health_input))

    def test_is_instance_healthy_false(self):
        autoscaling = AutoScaling(self.env)
        fake_health_input = {
            'HealthStatus': 'not_healthy',
            'LifecycleState': 'InService'
        }
        self.assertTrue(autoscaling._AutoScaling__is_instance_health(fake_health_input))

    