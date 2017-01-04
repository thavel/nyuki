import asyncio
import json
import websockets
from nose.tools import eq_, assert_raises, assert_in, assert_not_in
from unittest import TestCase
from unittest.mock import Mock

from nyuki import Nyuki
from nyuki.websocket import WebsocketResource, WebsocketHandler


class CustomResource(WebsocketResource):

    async def ready(self, client):
        return {'header': client.request_headers['X-Header']}


class TimeoutResource(WebsocketResource):

    KEEPALIVE = 0.01

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = asyncio.Event()

    async def close(self, client):
        self.event.set()


class WebsocketTest(TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.server = WebsocketHandler(Mock())
        self.server.configure()
        self.loop.run_until_complete(self.server.start())

    def tearDown(self):
        self.loop.run_until_complete(self.server.stop())
        self.loop.close()

    def test_001_client_connection(self):
        # No endpoint
        conn = self.loop.run_until_complete(websockets.connect(
            'ws://localhost:5559/some/url',
            extra_headers={'X-Header': 'some header'}
        ))
        with assert_raises(websockets.ConnectionClosed) as ctx:
            self.loop.run_until_complete(conn.recv())
        eq_(ctx.exception.code, 4004)

        assert_not_in('/some/url', WebsocketHandler.RESOURCES)
        res = CustomResource('/some/url')
        assert_in('/some/url', WebsocketHandler.RESOURCES)

        # Connect
        conn = self.loop.run_until_complete(websockets.connect(
            'ws://localhost:5559/some/url',
            extra_headers={'X-Header': 'some header'}
        ))
        eq_(len(res._clients), 1)

        # Receive the 'ready' payload
        msg = self.loop.run_until_complete(conn.recv())
        msg = json.loads(msg)
        eq_(msg, {
            'type': 'ready',
            'keepalive_delay': 48,
            'data': {'header': 'some header'}
        })

        # Receive a broadcast
        self.loop.run_until_complete(res.broadcast({'some': 'payload'}))
        msg = self.loop.run_until_complete(conn.recv())
        msg = json.loads(msg)
        eq_(msg, {'some': 'payload'})

        # Receive a custom message
        self.loop.run_until_complete(
            res._clients[0].send(b'{"something":"personal"}')
        )
        msg = self.loop.run_until_complete(conn.recv())
        msg = json.loads(msg)
        eq_(msg, {'something': 'personal'})

        # Disconnect
        self.loop.run_until_complete(conn.close(1000))
        with assert_raises(websockets.ConnectionClosed) as ctx:
            self.loop.run_until_complete(conn.recv())
        eq_(ctx.exception.code, 1000)
        eq_(len(res._clients), 0)

    def test_002_client_timeout(self):
        res = TimeoutResource('/timeout')

        # Connect
        conn = self.loop.run_until_complete(websockets.connect(
            'ws://localhost:5559/timeout'
        ))
        eq_(len(res._clients), 1)

        # Receive the 'ready' payload
        msg = self.loop.run_until_complete(conn.recv())
        msg = json.loads(msg)
        eq_(msg, {
            'type': 'ready',
            'keepalive_delay': 0.008,
            'data': {}
        })

        # One keepalive
        async def keepalive():
            await asyncio.sleep(0.008)
            await conn.send(json.dumps({'type': 'keepalive'}))
        self.loop.run_until_complete(keepalive())
        eq_(len(res._clients), 1)

        # Wait for timeout
        with assert_raises(websockets.ConnectionClosed) as ctx:
            self.loop.run_until_complete(conn.recv())
        eq_(ctx.exception.code, 4008)
        eq_(len(res._clients), 0)

    def test_003_multiple_clients(self):
        res = CustomResource('/some/url')
        tasks = [
            asyncio.ensure_future(websockets.connect(
                'ws://localhost:5559/some/url',
                extra_headers={'X-Header': 'some header'}
            ))
            for _ in range(0, 500)
        ]

        self.loop.run_until_complete(asyncio.wait(tasks))
        eq_(len(res._clients), 500)
        self.loop.run_until_complete(res.close_clients())
        eq_(len(res._clients), 0)

    def test_004_end_resource(self):
        res = CustomResource('/some/url')
        assert_in('/some/url', WebsocketHandler.RESOURCES)

        # Connect
        conn = self.loop.run_until_complete(websockets.connect(
            'ws://localhost:5559/some/url',
            extra_headers={'X-Header': 'some header'}
        ))
        eq_(len(res._clients), 1)

        # Receive the 'ready' payload
        msg = self.loop.run_until_complete(conn.recv())
        msg = json.loads(msg)
        eq_(msg, {
            'type': 'ready',
            'keepalive_delay': 48,
            'data': {'header': 'some header'}
        })

        # End resource
        res.end()
        with assert_raises(websockets.ConnectionClosed) as ctx:
            self.loop.run_until_complete(conn.recv())
        eq_(ctx.exception.code, 1001)
        assert_not_in('/some/url', WebsocketHandler.RESOURCES)
