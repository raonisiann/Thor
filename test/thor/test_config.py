from unittest import TestCase
from unittest.mock import patch
from thor.config import Config


class TestConfig(TestCase):

    def test_config_file_available(self):
        test_config = {
            "aws_region": "us-east-1",
            "auto_scaling_settings": {
                "description": "dummy description",
                "ami_id": "ami-xxxxxxxxxxx",
                "instance_type": "t2_mock",
                "key_pair": "mocked_kp",
                "availability_zone_names": [
                    "az_1",
                    "az_2"
                ],
                "subnet_ids": [
                    "subnet_1",
                    "subnet_2",
                    "subnet_3"
                ],
                "lb_target_group": "fake-lb-target-group",
                "health_check": {
                    "health_check_type": "ec2",
                    "health_check_grace_period": 300
                },
                "min_capacity": 1,
                "max_capacity": 1
            }
        }

        with patch('thor.config.Config.load_config_file', return_value=test_config):
            config = Config('/fake/path/to/config.json')
            # testing valid configs
            self.assertEqual(config.get('aws_region'), 'us-east-1')
            self.assertEqual(config.get('auto_scaling_settings.description'), 'dummy description')
            self.assertEqual(config.get('auto_scaling_settings.ami_id'), 'ami-xxxxxxxxxxx')
            self.assertEqual(config.get('auto_scaling_settings.instance_type'), 't2_mock')
            self.assertEqual(config.get('auto_scaling_settings.key_pair'), 'mocked_kp')
            self.assertTrue(type(config.get('auto_scaling_settings.availability_zone_names')) is list)
            self.assertTrue(type(config.get('auto_scaling_settings.subnet_ids')) is list)
            self.assertEqual(config.get('auto_scaling_settings.lb_target_group'), 'fake-lb-target-group')
            self.assertEqual(config.get('auto_scaling_settings.health_check.health_check_type'), 'ec2')
            self.assertEqual(config.get('auto_scaling_settings.health_check.health_check_grace_period'), 300)
            self.assertEqual(config.get('auto_scaling_settings.min_capacity'), 1)
            self.assertEqual(config.get('auto_scaling_settings.max_capacity'), 1)
            # testing unknow config setting
            self.assertIsNone(config.get('undefined.setting'))

    def test_config_file_not_available(self):
        with patch('thor.config.Config.load_config_file', return_value=None):
            config = Config('/fake/path/to/config.json')
            self.assertIsNone(config.get('undefined.setting'))
