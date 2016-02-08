import asyncio
from asynctest import TestCase, patch, exhaust_callbacks
import json
from nose.tools import eq_, assert_raises, assert_in, assert_not_in
from websockets import client, exceptions

from nyuki import Nyuki
from nyuki.websocket import websocket_ready


class WebNyuki(Nyuki):

    @websocket_ready
    async def ready(self):
        return {'test': 'ready'}


class WebsocketTest(TestCase):

    async def setUp(self):
        with patch('nyuki.config.read_default_json') as mock:
            mock.return_value = {}
            self.nyuki = WebNyuki(websocket={})

    async def tearDown(self):
        await self.client.close()
        await self.nyuki.websocket.stop()

    async def test_001_connection(self):
        # Init nyuki
        self.nyuki.websocket.configure('0.0.0.0', 5566, 600)
        web = self.nyuki.websocket
        await self.nyuki.websocket.start()

        # Bad token
        self.client = await client.connect('ws://localhost:5566/not_a_token')
        with assert_raises(exceptions.ConnectionClosed):
            await self.client.recv()

        # Create token using API
        resp = self.nyuki.WebsocketToken.get(self.nyuki, None)
        token = json.loads(resp.body.decode())['token']
        assert_in(token, web._tokens)

        # Good token
        self.client = await client.connect('ws://localhost:5566/' + token)
        await web.broadcast({'test': 'hello'})
        msg = json.loads(await self.client.recv())
        eq_(msg, {
            'data': {'test': 'ready'},
            'keepalive_delay': 480,
            'type': 'ready'
        })

        # Token already in use
        eq_(len(web.server.websockets), 1)
        await client.connect('ws://localhost:5566/' + token)
        await exhaust_callbacks(self.loop)
        eq_(len(web.server.websockets), 1)

        # Close connection
        await self.client.close()
        assert_not_in(token, web._tokens)

    async def test_002_keepalive(self):
        # Init nyuki
        self.nyuki.websocket.configure('0.0.0.0', 5566, 0.1)
        web = self.nyuki.websocket
        await self.nyuki.websocket.start()

        # Generate token
        token = web.new_token()

        # Connect
        self.client = await client.connect('ws://localhost:5566/' + token)
        assert_in(token, web._tokens)
        await asyncio.sleep(0.06)
        assert_in(token, web._tokens)
        await self.client.send(json.dumps({'type': 'keepalive'}))

        # Token expire
        await asyncio.sleep(0.06)
        assert_in(token, web._tokens)
        await asyncio.sleep(0.06)
        assert_not_in(token, web._tokens)
