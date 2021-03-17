from thor.lib.deploy import (
    DeployLock,
    DeployLockAlreadyAcquiredException
)
from thor.lib.env import Env
from thor.lib.image import Image
from unittest import TestCase


class MockImageParams():
    def __init__(self):
        self.deploy_lock = None


class TestDeployLock(TestCase):

    def setUp(self):
        self.fake_env = Env('fake')
        self.fake_image = Image(self.fake_env, 'fake_image')

    def test_lock_acquired(self):
        self.fake_image.params = MockImageParams()
        deploy_lock = DeployLock(self.fake_image)
        self.assertIsInstance(deploy_lock.acquire(), DeployLock)
        self.assertEqual(deploy_lock.lock, self.fake_image.params.deploy_lock)

    def test_lock_already_acquired(self):
        self.fake_image.params = MockImageParams()
        self.fake_image.params.deploy_lock = 'test-already-acquired'
        deploy_lock = DeployLock(self.fake_image)
        with self.assertRaises(DeployLockAlreadyAcquiredException):
            deploy_lock.acquire()

    def test_release(self):
        self.fake_image.params = MockImageParams()
        self.fake_image.params.deploy_lock = 'test'
        deploy_lock = DeployLock(self.fake_image)
        deploy_lock.lock = 'test'
        deploy_lock.release()
        self.assertEqual(deploy_lock.lock, '')
