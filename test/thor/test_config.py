from thor.lib.config import (
    Config,
    ConfigUnknownKeyException
)
from unittest import TestCase


class TestConfig(TestCase):

    def setUp(self):
        test_config = {
            "aws_region": "us-east-1",
            "asg": {
                "text": "dummy description",
                "ami_id": "ami-xxxxxxxxxxx",
                "instance_type": "t2_mock",
                "key_pair": "mocked_kp",
                "az_names": [
                    "az_1",
                    "az_2"
                ],
                "subnet_ids": [
                    "subnet_1",
                    "subnet_2",
                    "subnet_3"
                ],
                "lb_tg": "fake-lb-target-group",
                "hc": {
                    "type": "ec2",
                    "value": 300
                },
                "min_capacity": 1,
                "max_capacity": 1
            }
        }

        self.config = Config('/fake/path/to/config.json')
        self.config.loaded_config = test_config

    def test_get_config_available(self):
        # testing valid configs
        self.assertEqual(self.config.get('aws_region'), 'us-east-1')
        self.assertEqual(self.config.get('asg.text'), 'dummy description')
        self.assertEqual(self.config.get('asg.ami_id'), 'ami-xxxxxxxxxxx')
        self.assertEqual(self.config.get('asg.instance_type'), 't2_mock')
        self.assertEqual(self.config.get('asg.key_pair'), 'mocked_kp')
        self.assertEqual(self.config.get('asg.az_names.0'), 'az_1')
        self.assertEqual(self.config.get('asg.az_names.1'), 'az_2')
        self.assertEqual(self.config.get('asg.lb_tg'), 'fake-lb-target-group')
        self.assertEqual(self.config.get('asg.hc.type'), 'ec2')
        self.assertEqual(self.config.get('asg.hc.value'), 300)
        self.assertEqual(self.config.get('asg.min_capacity'), 1)
        self.assertEqual(self.config.get('asg.max_capacity'), 1)

    def test_config_data_types(self):
        self.assertTrue(type(self.config.get('aws_region')) is str)
        self.assertTrue(type(self.config.get('asg')) is dict)
        self.assertTrue(type(self.config.get('asg.az_names')) is list)
        self.assertTrue(type(self.config.get('asg.subnet_ids')) is list)
        self.assertTrue(type(self.config.get('asg.hc')) is dict)
        self.assertTrue(type(self.config.get('asg.hc.value')) is int)

    def test_get_config_not_available(self):
        with self.assertRaises(ConfigUnknownKeyException):
            self.assertIsNone(self.config.get('undefined.setting'))

    def test_set_config(self):
        self.config.set('new', 'new_value')
        self.config.set('new_list', [1, 2, 3])
        self.config.set('new_dict', {'a': '1'})
        self.config.set('complete.new.path', 'itsokay')
        self.config.set('another.new.list', ['', ''])
        self.config.set('another.new.list.0', 'a')
        self.config.set('another.new.list.1', 'b')

        self.assertListEqual(self.config.get('new_list'), [1, 2, 3])
        self.assertListEqual(self.config.get('another.new.list'), ['a', 'b'])
        self.assertDictEqual(self.config.get('new_dict'), {'a': '1'})
        self.assertEqual(self.config.get('new'), 'new_value')
        self.assertEqual(self.config.get('complete.new.path'), 'itsokay')
