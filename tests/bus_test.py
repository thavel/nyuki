from aiohttp import ClientOSError
import asyncio
import json
from mock import patch, Mock
from nose.tools import (
    assert_in, assert_is_none, assert_raises, assert_true, eq_)
from slixmpp.exceptions import IqError, IqTimeout
from unittest import TestCase
from xml.sax.saxutils import escape

from nyuki.bus import _BusClient, Bus
from nyuki.events import Event
from nyuki.loop import EventLoop

from tests import AsyncTestCase, fake_future


class TestBusClient(TestCase):

    def setUp(self):
        self.client = _BusClient('login@localhost', 'password')

    def test_001a_init(self):
        # Ensure bus client instanciation (method 1)
        host, port = self.client._address
        eq_(host, 'localhost')
        eq_(port, 5222)

    def test_001b_init(self):
        # Ensure bus client instanciation (method 2)
        client = _BusClient('login', 'password', '127.0.0.1', 5555)
        host, port = client._address
        eq_(host, '127.0.0.1')
        eq_(port, 5555)


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
        assert_in(Event.Connected, self.events)

    def test_002_disconnect(self):
        # When the callback _on_disconnect is called, an event is triggered.
        self.bus._on_disconnect(None)
        assert_in(Event.Disconnected, self.events)

    def test_003_failure(self):
        # When the callback _on_failure is called, an event is triggered.
        self.bus._on_failure(None)
        assert_in(Event.ConnectionError, self.events)

    def test_004_on_event(self):
        # Message without a subject will trigger a ResponseReceived.
        # Also test the proper Response stanza format
        msg = self.bus.client.Message()
        msg['type'] = 'groupchat'
        msg['body'] = json.dumps({'key': 'value'})
        self.bus._on_event(msg)
        encoded_xml = escape('{"key": "value"}', entities={'"': '&quot;'})
        assert_in(encoded_xml, str(msg))
        assert_in(Event.EventReceived, self.events)

    def test_005_bus_no_loop(self):
        with assert_raises(TypeError):
            Bus('jid', 'password')

    def test_006_muc_address(self):
        muc = self.bus._muc_address('topic')
        eq_(muc, 'topic@mucs.localhost')

    @patch('slixmpp.xmlstream.stanzabase.StanzaBase.send')
    def test_007a_publish(self, send_mock):
        with patch.object(self.bus, 'subscribe') as sub_mock:
            self.bus.publish({'message': 'test'})
            send_mock.assert_called_once_with()

    def test_007b_publish_no_dict(self):
        assert_raises(TypeError, self.bus.publish, 'not a dict')

    def test_008_subscribe(self):
        with patch.object(self.bus._mucs, 'joinMUC') as mock:
            self.bus.subscribe('login')
            mock.assert_called_once_with('login@mucs.localhost', 'login')

    @patch('slixmpp.stanza.Iq.send')
    def test_009_on_register_callback(self, send_mock):
        future = asyncio.Future()
        future.set_exception(IqTimeout(None))
        m = Mock()
        m.add_done_callback = lambda f: f(future)
        send_mock.return_value = m
        self.bus._on_register(None)
        assert_in(Event.ConnectionError, self.events)

    def test_010a_handle_response(self):
        future = Mock()
        future.result.return_value = 200, {'response': 'text'}
        cb = Mock()
        with patch.object(self.bus._loop, 'async') as async:
            self.bus._handle_response(cb, future)
            async.assert_called_once_with(cb, 200, {'response': 'text'})

    def test_010b_handle_response_error(self):
        future = Mock()
        future.result.side_effect = ClientOSError()
        cb = Mock()
        with patch.object(self.bus._loop, 'async') as async:
            self.bus._handle_response(cb, future)
            eq_(async.call_count, 0)


class TestBusRequest(AsyncTestCase):

    def setUp(self):
        super().setUp()
        self.bus = Bus('login@localhost', 'login', loop=EventLoop())

    def test_001a_request(self):
        @fake_future
        def request(method, url, data, headers):
            eq_(method, 'get')
            eq_(url, 'url')
            eq_(data, '{"message": "text"}')
            eq_(headers, {'Content-Type': 'application/json'})
            m = Mock()
            m.status = 200
            @fake_future
            def to_dict():
                return {'response': 'text'}
            m.json = to_dict
            return m

        with patch('aiohttp.request', request):
            status, body = self._loop.run_until_complete(self.bus._request(
                'url', 'get', {'message': 'text'}
            ))
            eq_(status, 200)
            eq_(body, {'response': 'text'})

    def test_001b_request_no_json(self):
        @fake_future
        def request(method, url, data, headers):
            eq_(method, 'get')
            eq_(url, 'url')
            eq_(data, '{"message": "text"}')
            eq_(headers, {'Content-Type': 'application/json'})
            m = Mock()
            m.status = 200
            @fake_future
            def to_dict():
                raise ValueError
            m.json = to_dict
            return m

        with patch('aiohttp.request', request):
            status, body = self._loop.run_until_complete(self.bus._request(
                'url', 'get', {'message': 'text'}
            ))
            eq_(status, 200)
            eq_(body, {})
