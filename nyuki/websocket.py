import asyncio
from datetime import datetime
import json
from jsonschema import validate, ValidationError
import logging
import random
import re
import string
import websockets

from nyuki.services import Service


log = logging.getLogger(__name__)


class WebsocketClient:

    def __init__(self, token, websocket, path):
        self._token = token
        self._websocket = websocket
        self._path = path

    @property
    def token(self):
        return self._token

    @property
    def websocket(self):
        return self._websocket

    @property
    def path(self):
        return self._path

    def __repr__(self):
        return '<WebsocketClient {} at {}>'.format(self._token, hex(id(self)))


class WebHandler(Service):

    CONF_SCHEMA = {
        'type': 'object',
        'properties': {
            'websocket': {
                'type': 'object',
                'properties': {
                    'host': {'type': 'string'},
                    'port': {'type': 'integer', 'minimum': 1}
                }
            }
        }
    }

    TOKEN_USAGE_TIMEOUT = 10
    KEEPALIVE_SCHEMA = {
        'type': 'object',
        'required': ['type'],
        'properties': {
            'type': {
                'type': 'string',
                'minLength': 1
            }
        }
    }

    def __init__(self, nyuki, loop=None):
        self._nyuki = nyuki
        self._nyuki.register_schema(self.CONF_SCHEMA)
        self._loop = loop or asyncio.get_event_loop()
        self.host = None
        self.port = None
        self.server = None
        self.keepalive = None
        self.tokens = None
        self._serializer = None

        # Handlers
        self._ready_handlers = []
        self._close_handlers = []

    @property
    def serializer(self):
        return self._serializer

    @serializer.setter
    def serializer(self, serializer):
        """
        Set to add a serializer to JSON messages.
        """
        self._serializer = serializer

    async def start(self):
        """
        Start the websocket server
        """
        log.info("Starting websocket server on %s:%s", self.host, self.port)
        self.server = await websockets.serve(
            self._wshandler, self.host, self.port
        )
        self.tokens = {}

    def configure(self, host='0.0.0.0', port=5559, keepalive=60):
        self.host = host
        self.port = port
        self.keepalive = keepalive

    async def stop(self):
        if self.server:
            for ws in self.server.websockets:
                ws.close()
            self.server.close()
            await self.server.wait_closed()

    def add_ready_handler(self, ready):
        """
        Add a method to be ran on a new client connection.
        """
        if not asyncio.iscoroutinefunction(ready):
            raise ValueError('Ready handler not coroutine')
        self._ready_handlers.append(ready)

    def add_close_handler(self, close):
        """
        Add a method to be ran at the end of a client connection.
        """
        if not asyncio.iscoroutinefunction(close):
            raise ValueError('Close handler not coroutine')
        self._close_handlers.append(close)

    def new_token(self):
        """
        Random token using 30 digits/lowercases
        """
        token = ''.join(
            random.choice(string.ascii_letters + string.digits)
            for _ in range(30)
        )
        log.debug('New websocket token: %s', token)
        self.tokens[token] = None
        self._loop.call_later(
            self.TOKEN_USAGE_TIMEOUT, self._check_token_usage, token
        )
        return token

    async def send(self, clients, data, timeout=2.0):
        """
        Send data to a client or a list of clients.
        """
        if not isinstance(clients, list):
            clients = [clients]
        if not isinstance(data, str):
            data = json.dumps(data, default=self._serializer)

        tasks = [
            asyncio.ensure_future(client.websocket.send(data))
            for client in clients
        ]
        if not tasks:
            return

        log.debug('Sending to client list %s: %s', clients, data)
        await asyncio.wait(tasks, timeout=timeout)

    async def broadcast(self, data, timeout=2.0):
        """
        Send a message to every connected client.
        """
        if not isinstance(data, str):
            data = json.dumps(data, default=self._serializer)

        tasks = [
            asyncio.ensure_future(websocket.send(data))
            for websocket in self.server.websockets
        ]
        if not tasks:
            return

        log.debug('Sending to all WS clients: %s', data)
        await asyncio.wait(tasks, timeout=timeout)

    def _check_token_usage(self, token):
        """
        Delete token if never used
        """
        if token in self.tokens and self.tokens[token] is None:
            log.debug("token '%s' never used, deleting it", token)
            del self.tokens[token]

    async def _send_ready(self, client):
        """
        Send the 'ready' message to a client
        """
        self.tokens[client.token] = client
        ready = {
            'type': 'ready',
            'keepalive_delay': self.keepalive * 0.8,
            'data': {}
        }
        for handler in self._ready_handlers:
            ready['data'] = await handler(client) or {}
        log.debug('Sending ready packet: %s', ready)
        await client.websocket.send(json.dumps(ready, default=self._serializer))

    async def _end_websocket_client(self, client, reason):
        """
        Close the connection if no keepalive have been received
        """
        tasks = [
            asyncio.ensure_future(handler(client))
            for handler in self._close_handlers
        ]
        if tasks:
            await asyncio.wait(tasks)
        client.websocket.close(reason=reason)
        try:
            del self.tokens[client.token]
        except KeyError as ke:
            log.debug('Token %s already removed from keepalive', ke)

    def _schedule_keepalive(self, client):
        return self._loop.call_later(
            self.keepalive,
            lambda: asyncio.ensure_future(self._end_websocket_client(
                client, 'keepalive timed out'
            ), loop=self._loop)
        )

    async def _wshandler(self, websocket, path):
        """
        Main handler for a newly connected client
        """
        match = re.match(r'^\/(?P<token>[a-zA-Z0-9]{30})$', path)
        if not match:
            log.debug('token does not match (%s)', path)
            websocket.close()
            return

        token = match.group('token')
        if token not in self.tokens:
            log.debug("Unknown token '%s'", token)
            websocket.close()
            return
        elif self.tokens[token] is not None:
            log.debug("Token already in use: '%s'", token)
            websocket.close()
            return

        log.info('Connection from token: %s', token)
        client = WebsocketClient(token, websocket, path)
        handle = self._schedule_keepalive(client)
        await self._send_ready(client)

        while True:
            # Main read loop
            try:
                message = await websocket.recv()
            except websockets.exceptions.ConnectionClosed as exc:
                log.debug('client connection closed: %s', exc)
                break

            # Decode JSON message
            try:
                data = json.loads(message)
            except ValueError:
                log.debug('Message received not JSON: %s', message)
                continue

            try:
                validate(data, self.KEEPALIVE_SCHEMA)
            except ValidationError:
                log.debug('Invalid keepalive received: %s', data)
                continue

            mtype = data['type']
            if mtype == 'keepalive':
                handle.cancel()
                handle = self._schedule_keepalive(client)

        handle.cancel()
        await self._end_websocket_client(client, 'connection closed normally')
