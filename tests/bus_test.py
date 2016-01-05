from aiohttp import ClientOSError
import asyncio
from nose.tools import assert_raises, eq_, ok_, assert_true, assert_false
from slixmpp import JID
from slixmpp.exceptions import IqTimeout
from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock

from nyuki.bus import _BusClient, Bus
from tests import make_future, future_func, AsyncMock


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
        self.loop = asyncio.get_event_loop()
        self.bus = Bus(Mock())
        self.bus.configure('login@localhost', 'password')

    def test_001_muc_address(self):
        muc = self.bus._muc_address('topic')
        eq_(muc, 'topic@mucs.localhost')

    def test_002_on_event(self):
        cb = Mock(return_value=make_future())
        with patch.object(self.bus._mucs, 'joinMUC') as join_mock:
            self.bus._connected.set()
            self.loop.run_until_complete(self.bus.subscribe('other', cb))
            join_mock.assert_called_once_with('other@mucs.localhost', 'login')
        msg = self.bus.client.Message()
        msg['type'] = 'groupchat'
        msg['from'] = JID('other@localhost')
        msg['body'] = '{"key": "value"}'
        self.loop.run_until_complete(self.bus._on_event(msg))
        cb.assert_called_once_with({'key': 'value'})

    @patch('slixmpp.xmlstream.stanzabase.StanzaBase.send')
    def test_003a_publish(self, send_mock):
        self.bus.publish({'message': 'test'})
        send_mock.assert_called_once_with()

    def test_003b_publish_no_dict(self):
        assert_raises(TypeError, self.bus.publish, 'not a dict')

    def test_004_on_register_callback(self):
        with patch('slixmpp.stanza.Iq.send', new=AsyncMock()) as send_mock:
            self.loop.run_until_complete(self.bus._on_register(None))
            send_mock.assert_called_once_with()

    def test_005_reconnect(self):
        with patch.object(self.bus.client, '_connect_routine', new=AsyncMock()) as mock:
            self.loop.run_until_complete(self.bus._on_disconnect(None))
            eq_(mock.call_count, 1)


class TestBusRequest(TestCase):

    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.bus = Bus(Mock())

    def test_001a_request(self):
        @future_func
        def request(method, url, data, headers):
            eq_(method, 'get')
            eq_(url, 'url')
            eq_(data, '{"message": "text"}')
            eq_(headers, {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            })
            m = Mock()
            m.status = 200
            @future_func
            def to_json():
                return {'response': 'text'}
            m.json = to_json
            return m

        with patch('aiohttp.request', request):
            response = self.loop.run_until_complete(
                self.bus._execute_request('url', 'get', {'message': 'text'})
                )
        eq_(response.status, 200)
        eq_(response.json, {'response': 'text'})

    def test_001b_request_no_json(self):
        @future_func
        def request(method, url, data, headers):
            eq_(method, 'get')
            eq_(url, 'url')
            eq_(data, '{"message": "text"}')
            eq_(headers, {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            })
            m = Mock()
            m.status = 200
            @future_func
            def to_json():
                raise ValueError
            m.json = to_json
            @future_func
            def to_text():
                return 'something'
            m.text = to_text
            return m

        with patch('aiohttp.request', request):
            response = self.loop.run_until_complete(
                self.bus._execute_request('url', 'get', {'message': 'text'})
                )
        eq_(response.status, 200)
        eq_(response.json, None)
        eq_(response.text().result(), 'something')

    def test_001c_request_error(self):
        error = {
            'endpoint': 'http://localhost:8080/None/api/url',
            'error': 'ClientOSError()',
            'data': {'message': 'text'}
        }
        with patch('aiohttp.request', side_effect=ClientOSError):
            with patch.object(self.bus, 'publish') as publish:
                exc = self.loop.run_until_complete(self.bus.request(
                    None, 'url', 'get',
                    data={'message': 'text'}
                ))
            publish.assert_called_once_with(error)
            ok_(isinstance(exc, ClientOSError))
