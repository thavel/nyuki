import json
from unittest import TestCase
from mock import Mock

from slixmpp.exceptions import XMPPError
from nyuki.bus import _BusClient, Bus, Formatter
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


class TestBus(TestCase):

    def setUp(self):
        self.events = list()
        self.bus = Bus('login@localhost', 'password')

        self.bus._event.trigger = (lambda x, *y: self.events.append(x))
        self.bus.client = Mock()

    def tearDown(self):
        self.events = list()

    def test_001_connection(self):
        # When the callback _on_connection is called, an event is triggered.
        self.bus._on_connection(None)
        self.assertIn(Event.Connecting, self.events)

    def test_002_start(self):
        # When the callback _on_start is called, an event is triggered.
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

    def test_005a_message(self):
        # Message that can't be decoded will trigger a MessageReceived event.
        event = dict()
        event['body'] = 'message'
        self.bus._on_message(event)
        self.assertIn(Event.MessageReceived, self.events)

    def test_005b_request(self):
        # Message with a subject (capability) will trigger a RequestReceived.
        event = dict()
        event['body'] = '{"message": "test"}'
        event['subject'] = 'update_message'
        self.bus._on_message(event)
        self.assertIn(Event.RequestReceived, self.events)

    def test_005c_response(self):
        # Message without a subject will trigger a ResponseReceived.
        event = dict()
        event['body'] = '{"message": "test"}'
        self.bus._on_message(event)
        self.assertIn(Event.ResponseReceived, self.events)


class TestFormatter(TestCase):

    def setUp(self):
        self.from_jid = 'login@host'
        self.formatter = Formatter(_BusClient(self.from_jid, 'password'))

    def test_001_format(self):
        # Format is working properly
        result = self.formatter._format({'message': 'hello'})
        self.assertIsInstance(result, str)
        self.assertRaises(TypeError, self.formatter._format, 'hello')

    def test_002_reply(self):
        # Create a valid response for a given request
        to_jid = 'sender@host'
        resp_body = {'status': 200}
        request = self.formatter.unicast({'message': 'hello'}, to_jid, 'test')
        response = self.formatter.reply(request, resp_body)
        self.assertEqual(response['body'], json.dumps(resp_body))

    def test_003_unicast(self):
        msg = self.formatter.unicast({'message': 'hello'}, 'login@host', 'test')
        self.assertIsInstance(msg['body'], str)
