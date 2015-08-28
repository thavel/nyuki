import json
from unittest import TestCase
from mock import Mock, patch, MagicMock
from slixmpp.exceptions import XMPPError
from xml.sax.saxutils import escape

from nyuki.bus import _BusClient, Bus
from nyuki.events import Event
from nyuki.loop import EventLoop


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


@patch('nyuki.bus.Bus', 'connect')
class TestBus(TestCase):

    def setUp(self):
        self.events = list()
        self.bus = Bus('login@localhost', 'password', loop=EventLoop())
        self.bus.event_manager.trigger = (lambda x, *y: self.events.append(x))

    def tearDown(self):
        self.events = list()

    def test_001_start(self):
        # When the callback _on_start is called, an event is triggered.
        with patch.object(self.bus, 'client'):
            self.bus._on_start(None)
        self.assertIn(Event.Connected, self.events)

    def test_002_disconnect(self):
        # When the callback _on_disconnect is called, an event is triggered.
        self.bus._on_disconnect(None)
        self.assertIn(Event.Disconnected, self.events)

    def test_003_failure(self):
        # When the callback _on_failure is called, an event is triggered.
        self.bus._on_failure(None)
        self.assertIn(Event.ConnectionError, self.events)

    def test_004_on_event(self):
        # Message without a subject will trigger a ResponseReceived.
        # Also test the proper Response stanza format
        msg = self.bus.client.Message()
        msg['type'] = 'groupchat'
        msg['body'] = json.dumps({'key': 'value'})
        self.bus._on_event(msg)
        encoded_xml = escape('{"key": "value"}', entities={'"': '&quot;'})
        self.assertIn(encoded_xml, str(msg))
        self.assertIn(Event.EventReceived, self.events)

    def test_005_bus_no_loop(self):
        with self.assertRaises(TypeError):
            Bus('jid', 'password')

    def test_006_muc_address(self):
        muc = self.bus._muc_address('topic')
        self.assertEqual(muc, 'topic@mucs.localhost')

    @patch('slixmpp.xmlstream.stanzabase.StanzaBase.send')
    def test_007a_publish(self, sendmock):
        with patch.object(self.bus, 'subscribe') as submock:
            self.bus.publish({'message': 'test'})
            submock.assert_called_once_with(self.bus._topic)
            sendmock.assert_called_once_with()

    def test_007b_publish_no_dict(self):
        self.assertIs(self.bus.publish('not a dict'), None)

    def test_008_subscribe(self):
        with patch.object(self.bus._mucs, 'joinMUC') as mock:
            self.bus.subscribe('login')
            mock.assert_called_once_with('login@mucs.localhost', 'login')
