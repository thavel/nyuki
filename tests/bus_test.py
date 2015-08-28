import json
from unittest import TestCase
from mock import Mock, patch, MagicMock
from slixmpp.exceptions import XMPPError
from xml.sax.saxutils import escape

from nyuki.bus import _BusClient, Bus
from nyuki.events import Event


class TestBusClient(TestCase):

    def setUp(self):
        self.client = _BusClient('login@localhost', 'password')

    def test_001a_init(self):
        # Ensure bus client instanciation (method 1)
        host, port = self.client._address
        self.assertEqual(host, 'localhost')
        self.assertEqual(port, 5222)

    def test_001b_init(self):
        # Ensure bus client instanciation (method 2)
        client = _BusClient('login', 'password', '127.0.0.1', 5555)
        host, port = client._address
        self.assertEqual(host, '127.0.0.1')
        self.assertEqual(port, 5555)

    def test_001c_init_error(self):
        # Ensure bus client needs a valid host (from the jid or as a parameter)
        self.assertRaises(XMPPError, _BusClient, 'login', 'password')


@patch('nyuki.bus.Bus', 'connect')
class TestBus(TestCase):

    def setUp(self):
        self.events = list()
        self.bus = Bus('login@localhost', 'password')
        self.bus._event.trigger = (lambda x, *y: self.events.append(x))

    def tearDown(self):
        self.events = list()

    def test_001_connection(self):
        # When the callback _on_connection is called, an event is triggered.
        self.bus._on_connection(None)
        self.assertIn(Event.Connecting, self.events)

    def test_002_start(self):
        # When the callback _on_start is called, an event is triggered.
        with patch.object(self.bus, 'client'):
            self.bus._on_start(None)
        self.assertIn(Event.Connected, self.events)

    def test_003_disconnect(self):
        # When the callback _on_disconnect is called, an event is triggered.
        self.bus._on_disconnect(None)
        self.assertIn(Event.Disconnected, self.events)

    def test_004_failure(self):
        # When the callback _on_failure is called, an event is triggered.
        self.bus._on_failure(None)
        self.assertIn(Event.ConnectionError, self.events)

    def test_005_on_event(self):
        # Message without a subject will trigger a ResponseReceived.
        # Also test the proper Response stanza format
        msg = self.bus.client.Message()
        msg['type'] = 'groupchat'
        msg['response']['json'] = {'key': 'value'}
        msg['response']['status'] = 200
        self.bus._on_event(msg)
        encoded_xml = escape('{"key": "value"}', entities={'"': '&quot;'})
        self.assertIn(encoded_xml, str(msg))
        self.assertIn('200', str(msg))
        self.assertIn(Event.EventReceived, self.events)
