from unittest import TestCase
from mock import Mock

from nyuki.events import EventManager, Event, on_event


class TestOnEvent(TestCase):

    def test_001_call(self):
        @on_event(Event.Connected, Event.Disconnected)
        def test():
            pass
        self.assertIsInstance(test.on_event, set)


class TestEventManager(TestCase):

    def setUp(self):
        self.loop = Mock()
        self.manager = EventManager(self.loop)

    def test_001_init(self):
        # Ensure callback tree has been properly setup
        self.assertCountEqual(self.manager._callbacks.keys(), list(Event))

    def test_002a_register(self):
        # For all kind of event, we're ensure we can add a callback
        for event in Event:
            callback = (lambda x: x)
            self.manager.register(event, callback)
            self.assertIn(callback, self.manager._callbacks[event])

    def test_002b_register_error(self):
        # Here's what happens when the specified event does not exists
        event = Mock()
        callback = (lambda x: x)
        self.assertRaises(ValueError, self.manager.register, event, callback)

    def test_003a_trigger(self):
        # Ensure callbacks are properly scheduled when an event is triggered
        callbacks = list()
        self.loop.async = (lambda c, *args: callbacks.append(c))
        cb = (lambda x: x)
        self.manager.register(Event.Connected, cb)
        self.manager.trigger(Event.Connected)
        self.assertIn(cb, callbacks)

    def test_003b_trigger_error(self):
        # Ensure we can not trigger an event that does not exists
        event = Mock()
        self.assertRaises(ValueError, self.manager.trigger, event)
