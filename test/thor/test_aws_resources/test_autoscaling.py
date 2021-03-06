from thor.lib.aws_resources.autoscaling import AutoScaling
from thor.lib.env import Env
from unittest import TestCase


class TestAutoScalingGroup(TestCase):

    def setUp(self):
        self.env = Env('test')

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
        self.assertFalse(autoscaling._AutoScaling__is_instance_health(fake_health_input))
