import types
import inspect
from unittest import TestCase

from nyuki.handlers import CapabilityHandler, EventHandler
from nyuki.capabilities import resource
from nyuki.events import on_event, Event


class Registry(object):
    REG = list()

    def register(self, obj, other=None):
        self.REG.append(obj)


class TestCapabilityHandler(TestCase):

    # Test class
    class Test(metaclass=CapabilityHandler):
        capability_exposer = Registry()

        # Test resource
        @resource('/list', 'v1')
        class List:
            # Test method
            def get(self):
                pass

    def setUp(self):
        self.test = self.Test()

    def tearDown(self):
        self.test.capability_exposer.REG = list()

    def test_001_filter_resource(self):
        gen = CapabilityHandler._filter_resource(self.test)
        self.assertIsInstance(gen, types.GeneratorType)
        for name, cls in gen:
            self.assertIsInstance(name, str)
            self.assertTrue(inspect.isclass(cls))

    def test_002_filter_capability(self):
        gen = CapabilityHandler._filter_capability(self.test.List)
        self.assertIsInstance(gen, types.GeneratorType)
        for method, handler in gen:
            self.assertIsInstance(method, str)
            self.assertTrue(inspect.isfunction(handler))

    def test_003_call(self):
        registry = self.test.capability_exposer.REG
        self.assertEqual(len(registry), 1)


class TestEventHandler(TestCase):

    # Test class
    class Test(metaclass=EventHandler):
        event_manager = Registry()

        # Test handler
        @on_event(Event.Connected)
        def test(self):
            pass

    def setUp(self):
        self.test = self.Test()

    def tearDown(self):
        self.test.event_manager.REG = list()

    def test_001_filter_event(self):
        gen = EventHandler._filter_event(self.test)
        self.assertIsInstance(gen, types.GeneratorType)
        for handler, events in gen:
            self.assertIsInstance(events, set)
            self.assertTrue(callable(handler))

    def test_002_call(self):
        registry = self.test.event_manager.REG
        self.assertEqual(len(registry), 1)

