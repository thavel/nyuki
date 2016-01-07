from asynctest import TestCase, MagicMock, exhaust_callbacks
from nose.tools import assert_true, assert_false

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
        self.manager = ServiceManager(MagicMock())
        self.manager.add('test1', FakeService())
        self.manager.add('test2', FakeService())

    async def test_001_start_stop_all(self):
        await self.manager.start()
        assert_true(self.manager.get('test1').started)
        assert_true(self.manager.get('test2').started)

        # Add one on the way
        self.manager.add('test3', FakeService())
        # finish coroutines
        await exhaust_callbacks(self.loop)
        assert_true(self.manager.get('test3').started)

        await self.manager.stop()
        assert_false(self.manager.get('test1').started)
        assert_false(self.manager.get('test2').started)
        assert_false(self.manager.get('test3').started)
