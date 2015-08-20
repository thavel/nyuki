from unittest import TestCase
from mock import Mock

from nyuki.events import EventManager, Event, on_event


class Loop(Mock):
    STACK = list()

    def async(self, cb, *args):
        self.STACK.append(cb)



class TestEventManager(TestCase):

    def setUp(self):
        loop = Mock()
        self.manager = EventManager(loop)

    def test_001_init(self):
        # Ensure callback tree has been properly setup.
        self.assertCountEqual(self.manager._callbacks.keys(), list(Event))

    def test_002a_register(self):
        pass

    def test_002b_register_error(self):
        pass

    def test_003a_trigger(self):
        pass

    def test_003b_trigger_error(self):
        pass

    def tearDown(self):
        pass