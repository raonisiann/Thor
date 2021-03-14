from thor.lib.aws_resources.parameter_store import ParameterStoreAlreadyExistsException
from thor.lib.deploy import (
    DeployLock,
    DeployLockAlreadyAcquiredException
)
from thor.lib.env import Env
from thor.lib.image import Image
from unittest import TestCase
from unittest.mock import patch, Mock


class TestDeployLock(TestCase):

    def setUp(self):
        self.fake_env = Env('fake')
        self.fake_image = Image(self.fake_env, 'fake_image')

    @patch('thor.lib.deploy.ParameterStore')
    def test_lock_acquired(self, mock_param):
        deploy_lock = DeployLock(self.fake_image)
        mock_param.create.return_value = 'created'
        self.assertIsInstance(deploy_lock.acquire(), DeployLock)

    @patch('thor.lib.deploy.ParameterStore.create', Mock(side_effect=ParameterStoreAlreadyExistsException()))
    def test_lock_already_acquired(self):
        deploy_lock = DeployLock(self.fake_image)
        with self.assertRaises(DeployLockAlreadyAcquiredException):
            deploy_lock.acquire()
            mock_param.create.assert_called_once()

    @patch('thor.lib.deploy.ParameterStore')
    def test_release(self, mock_param):
        deploy_lock = DeployLock(self.fake_image)
        mock_param.destroy.return_value = 'deleted'
        deploy_lock.lock = 'test'
        deploy_lock.release()
        self.assertEqual(deploy_lock.lock, '')