from mock import patch, MagicMock
from unittest import TestCase

from nyuki.messaging.event import Event, EventManager, on_event, Connected


class EventObject(object):

    def __init__(self):
        pass

    @on_event(Connected)
    def my_meth(self):
        return True

    def other_meth(self):
        return False


class TestEventManager(TestCase):

    def setUp(self):
        self.manager = EventManager()

    @patch.object(EventManager, 'add_handler')
    def test_001_register(self, mock):
        obj = EventObject()
        self.manager.register(obj)
        mock.assert_called_once_with(obj.my_meth)
        self.assertEqual(obj.fire, self.manager.fire)

    def test_002a_add_handler(self):
        def dummy():
            return True

        @on_event(Connected)
        def dummy_2(self):
            return False

        self.assertEqual(self.manager._handlers, {})
        self.manager.add_handler(dummy, Connected)

        self.assertTrue(dummy in self.manager._handlers[Connected])
        self.manager.add_handler(dummy_2)
        self.assertTrue(dummy in self.manager._handlers[Connected])
        self.assertTrue(dummy_2 in self.manager._handlers[Connected])

    def test_002b_add_handler_err(self):
        def dummy():
            return True
        with self.assertRaises(TypeError):
            self.manager.add_handler(dummy, object)

    def test_003a_fire(self):

        update = MagicMock()
        update_2 = MagicMock()

        methods = set()
        methods.add(update)
        methods.add(update_2)
        event = Event()

        self.manager._handlers[Event] = methods
        self.manager.fire(event)
        update.assert_called_once_with(event)
        update_2.assert_called_once_with(event)

    def test_003b_fire_err(self):
        with self.assertRaises(TypeError):
            self.manager.fire('test')
