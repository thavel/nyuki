import asyncio
from nose.tools import assert_true, assert_false
from unittest import TestCase
from unittest.mock import MagicMock

from nyuki.services import ServiceManager, Service


class FakeService(Service):

    def __init__(self):
        self.started = False

    async def start(self):
        self.started = True

    def configure(self):
        pass

    async def stop(self):
        self.started = False


class ServicesTest(TestCase):

    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.manager = ServiceManager(MagicMock())
        self.manager.add('test1', FakeService())
        self.manager.add('test2', FakeService())

    def test_001_start_stop_all(self):
        self.loop.run_until_complete(self.manager.start())
        assert_true(self.manager.get('test1').started)
        assert_true(self.manager.get('test2').started)

        # Add one on the way
        self.manager.add('test3', FakeService())
        # run the service start future
        self.loop.run_until_complete(asyncio.sleep(0))
        assert_true(self.manager.get('test3').started)

        self.loop.run_until_complete(self.manager.stop())
        assert_false(self.manager.get('test1').started)
        assert_false(self.manager.get('test2').started)
        assert_false(self.manager.get('test3').started)
