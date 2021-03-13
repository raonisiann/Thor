from unittest import TestCase
from unittest.mock import PropertyMock, MagicMock, patch
from thor.lib.env import Env
from thor.lib.image import Image


class TestImage(TestCase):

    def setUp(self):
        self.env = Env('test')
        self.image = Image(self.env, 'test')

    def test_rotate_ami_id_list(self):
        input_list = ['ami-3', 'ami-2', 'ami-1']
        new_ami = 'ami-4'
        result = self.image.rotate_ami_id_list(new_ami, input_list)
        self.assertEqual(result, 'ami-4,ami-3,ami-2,ami-1')

    def test_rotate_ami_id_list_first_ami(self):
        new_ami = 'ami-1'
        self.assertEqual(self.image.rotate_ami_id_list(new_ami, None),
                         'ami-1')
        self.assertEqual(self.image.rotate_ami_id_list(new_ami, []),
                         'ami-1')

    def test_rotate_ami_id_list_max_size(self):
        input_list = ['ami-10', 'ami-9', 'ami-8', 'ami-7','ami-6', 'ami-5',
                      'ami-4', 'ami-3', 'ami-2', 'ami-1']
        new_ami = 'ami-11'
        result = self.image.rotate_ami_id_list(new_ami, input_list)
        self.assertEqual(result, 'ami-11,ami-10,ami-9,ami-8,ami-7,'
                                 'ami-6,ami-5,ami-4,ami-3,ami-2')

    def test_get_latest_ami(self):
        self.image.params = MagicMock(ami_id_list=['ami-4', 'ami-3', 'ami-2', 'ami-1'])
        self.assertEqual('ami-4', self.image.get_latest_ami_id())
