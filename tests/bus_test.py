from aiohttp import ClientOSError
import asyncio
from asynctest import (
    TestCase, patch, Mock, CoroutineMock, ignore_loop, exhaust_callbacks
)
from nose.tools import assert_raises, eq_, ok_
from slixmpp import JID

from nyuki.bus import _BusClient, Bus
from tests import future_func


class TestBusClient(TestCase):

    def setUp(self):
        self.client = _BusClient('login@localhost', 'password')

    @ignore_loop
    def test_001a_init(self):
        # Ensure bus client instanciation (method 1)
        host, port = self.client._address
        eq_(host, 'localhost')
        eq_(port, 5222)

    @ignore_loop
    def test_001b_init(self):
        # Ensure bus client instanciation (method 2)
        client = _BusClient('login', 'password', '127.0.0.1', 5555)
        host, port = client._address
        eq_(host, '127.0.0.1')
        eq_(port, 5555)


@patch('nyuki.bus.Bus', 'connect')
class TestBus(TestCase):

    def setUp(self):
        self.bus = Bus(Mock())
        self.bus.configure('login@localhost', 'password')

    @ignore_loop
    def test_001_muc_address(self):
        muc = self.bus._muc_address('topic')
        eq_(muc, 'topic@mucs.localhost')

    async def test_002_on_event(self):
        cb = CoroutineMock()
        with patch.object(self.bus._mucs, 'joinMUC') as join_mock:
            self.bus._connected.set()
            await self.bus.subscribe('other', cb)
            join_mock.assert_called_once_with('other@mucs.localhost', 'login')
        msg = self.bus.client.Message()
        msg['type'] = 'groupchat'
        msg['from'] = JID('other@localhost')
        msg['body'] = '{"key": "value"}'
        await self.bus._on_event(msg)
        cb.assert_called_once_with({'key': 'value'})

    @patch('slixmpp.xmlstream.stanzabase.StanzaBase.send')
    async def test_003a_publish(self, send_mock):
        asyncio.ensure_future(self.bus.publish({'message': '1'}))
        asyncio.ensure_future(self.bus.publish({'message': '2'}))
        asyncio.ensure_future(self.bus.publish({'message': '3'}))
        # Waiting for connection
        eq_(send_mock.call_count, 0)
        self.bus._connected.set()
        await exhaust_callbacks(self.loop)
        eq_(send_mock.call_count, 3)

    async def test_003b_publish_no_dict(self):
        with assert_raises(TypeError):
            await self.bus.publish('not a dict')

    async def test_004_on_register_callback(self):
        with patch('slixmpp.stanza.Iq.send', new=CoroutineMock()) as send_mock:
            await self.bus._on_register(None)
            send_mock.assert_called_once_with()

    async def test_005_reconnect(self):
        self.bus.reconnect = True
        with patch.object(self.bus.client, '_connect_routine') as mock:
            await self.bus._on_disconnect(None)
            eq_(mock.call_count, 1)

    @patch('slixmpp.xmlstream.stanzabase.StanzaBase.send')
    async def test_006_direct_message(self, send_mock):
        self.bus._connected.set()
        await self.bus.send_message('yo', {'message': 'test'})
        send_mock.assert_called_once_with()

    async def test_007_on_direct_message(self):
        cb = CoroutineMock()
        self.bus.direct_subscribe(cb)
        msg = self.bus.client.Message()
        msg['type'] = 'message'
        msg['from'] = JID('other@localhost')
        msg['body'] = '{"key": "value"}'
        await self.bus._on_direct_message(msg)
        cb.assert_called_once_with('other', {'key': 'value'})
