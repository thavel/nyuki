import asyncio
from asynctest import TestCase, exhaust_callbacks
import json
from nose.tools import eq_, assert_raises, assert_in, assert_not_in
import tempfile
from websockets import client, exceptions

from nyuki import Nyuki
from nyuki.websocket import websocket_ready


class WebNyuki(Nyuki):

    @websocket_ready
    async def ready(self, token):
        return {'your_token': token}


class WebsocketTest(TestCase):

    async def setUp(self):
        conf = tempfile.NamedTemporaryFile('w')
        with open(conf.name, 'w') as f:
            f.write(json.dumps({
                'websocket': {}
            }))
        self.nyuki = WebNyuki(config=conf.name)

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
        assert_in(token, web.clients)

        # Good token
        self.client = await client.connect('ws://localhost:5566/' + token)
        await web.broadcast({'test': 'hello'})
        msg = json.loads(await self.client.recv())
        eq_(msg, {
            'data': {'your_token': token},
            'keepalive_delay': 480,
            'type': 'ready'
        })

        # Token already in use
        conn = list(web.server.websockets)[0]
        eq_(len(web.server.websockets), 1)
        await client.connect('ws://localhost:5566/' + token)
        for c in web.server.websockets:
            if c != conn:
                new_conn = c
                break
        await new_conn.handler_task
        eq_(len(web.server.websockets), 1)

        # Close connection
        await self.client.close()
        assert_not_in(token, web.clients)

    async def test_002_keepalive(self):
        # Init nyuki
        self.nyuki.websocket.configure('0.0.0.0', 5566, 0.1)
        web = self.nyuki.websocket
        await self.nyuki.websocket.start()

        # Generate token
        token = web.new_token()

        # Connect
        self.client = await client.connect('ws://localhost:5566/' + token)
        assert_in(token, web.clients)
        await asyncio.sleep(0.06)
        assert_in(token, web.clients)
        await self.client.send(json.dumps({'type': 'keepalive'}))

        # Token expire
        await asyncio.sleep(0.06)
        assert_in(token, web.clients)
        await asyncio.sleep(0.06)
        assert_not_in(token, web.clients)
