import types
import inspect
from unittest import TestCase

from nyuki.handlers import CapabilityHandler
from nyuki.capabilities import resource


class Registry(object):
    REG = list()

    def register(self, obj, other=None):
        self.REG.append(obj)


class Test(metaclass=CapabilityHandler):

    """
    Test class
    """

    api = Registry()

    @resource('/list', 'v1')
    class List:

        def get(self):
            pass


class TestCapabilityHandler(TestCase):

    def setUp(self):
        self.test = Test()

    def tearDown(self):
        self.test.api.REG = list()

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
        registry = self.test.api.REG
        self.assertEqual(len(registry), 1)
