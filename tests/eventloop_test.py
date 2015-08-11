from asyncio import get_event_loop
from mock import Mock
from unittest import TestCase

from nyuki.eventloop import EventLoop


class TestLooping(TestCase):

    def setUp(self):
        self.loop = EventLoop()

    def test_001_loop(self):
        self.assertFalse(self.loop.is_running())
        self.assertEqual(get_event_loop(), self.loop.loop)

    def test_002_start(self):
        self.loop.start(False)
        self.assertFalse(self.loop._blocking)
        self.assertTrue(self.loop.is_running())

    def test_003_stop(self):
        self.test_002_start()
        self.loop.stop()
        self.assertFalse(self.loop.is_running())

    def test_004_add_timeout(self):
        with self.assertRaises(KeyError):
            self.loop._timeouts['key']
        self.loop.add_timeout('key', 5, Mock)
        handle = self.loop._timeouts['key']
        self.assertEqual(handle._when, 5)
        handle._callback()
        with self.assertRaises(KeyError):
            self.loop._timeouts['key']

    def test_005_cancel_timeout(self):
        self.loop.add_timeout('key', 5, Mock)
        self.loop.cancel_timeout('key')
        with self.assertRaises(KeyError):
            self.loop._timeouts['key']

    def tearDown(self):
        if self.loop.is_running():
            self.loop.stop()
