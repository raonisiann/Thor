from unittest import TestCase
from unittest.mock import patch
from thor.deploy import DeployLock
from thor.env import Env
from thor.image import Image


class TestDeployLock(TestCase):

    def setUp(self):
        self.fake_env = Env('fake')
        self.fake_image = Image(self.fake_env, 'fake_image')

    @patch('thor.deploy.DeployLock.is_lock_acquired')
    def test_lock_acquired(self, mock_lock):
        deploy_lock = DeployLock(self.fake_image)
        mock_lock.return_value = True
        with patch('thor.deploy.Param.create'):
            self.assertTrue(deploy_lock.acquire())

    @patch('thor.deploy.DeployLock.is_lock_acquired')
    def test_lock_not_acquired(self, mock_lock):
        deploy_lock = DeployLock(self.fake_image)
        mock_lock.return_value = False
        with patch('thor.deploy.Param.create'):
            self.assertFalse(deploy_lock.acquire())
