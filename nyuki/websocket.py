import asyncio
import json
from jsonschema import validate, ValidationError
import logging
import random
import re
import string
import websockets

from nyuki.services import Service


log = logging.getLogger(__name__)


def websocket_ready(func):
    """
    This decorator set an async method to be called at a client connection,
    the return value (dict) and will be sent as data to the client
    """
    @staticmethod
    async def decorated(self, token):
        return await func(self, token)

    WebHandler.READY_CALLBACK = decorated
    return func


def websocket_close(func):
    """
    This decorator set an async method to be called at a client connection,
    the return value (dict) and will be sent as data to the client
    """
    @staticmethod
    async def decorated(self, token):
        return await func(self, token)

    WebHandler.CLOSE_CALLBACK = decorated
    return func


class WebHandler(Service):

    CONF_SCHEMA = {
        "type": "object",
        "properties": {
            "websocket": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"}
                }
            }
        }
    }

    READY_CALLBACK = None
    CLOSE_CALLBACK = None
    TOKEN_USAGE_TIMEOUT = 1
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
        self.clients = {}
        self._serializer = None

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

    def new_token(self):
        """
        Random token using 30 digits/lowercases
        """
        token = ''.join(
            random.choice(string.ascii_letters + string.digits)
            for _ in range(30)
        )
        log.debug('new token: %s', token)
        self.clients[token] = None
        self._loop.call_later(
            self.TOKEN_USAGE_TIMEOUT, self._check_token_usage, token
        )
        return token

    async def broadcast(self, message, tokens=None, timeout=2.0):
        """
        Send a message to every connected client
        """
        tasks = []
        if not isinstance(message, str):
            data = json.dumps(message, default=self._serializer)
        if isinstance(tokens, str):
            tokens = [tokens]
        if isinstance(tokens, list):
            log.debug('Sending to client list %s: %s', tokens, data)
            for token in tokens:
                client = self.clients[token]
                if client is None:
                    log.warning("Token '%s' initialized but not used", token)
                    continue
                tasks.append(asyncio.ensure_future(client.send(data)))
        else:
            log.debug('Sending to all WS clients: %s', data)
            for websocket in self.server.websockets:
                tasks.append(asyncio.ensure_future(websocket.send(data)))

        if not tasks:
            log.debug('Nobody to broadcast to')
            return

        await asyncio.wait(tasks, timeout=timeout)

    async def _send_ready(self, websocket, token):
        """
        Send the 'ready' message to a client
        """
        self.clients[token] = websocket
        ready = {
            'type': 'ready',
            'keepalive_delay': self.keepalive * 0.8,
            'data': {}
        }
        if self.READY_CALLBACK:
            log.info('Ready callback set up, calling it for new client')
            ready['data'] = await self.READY_CALLBACK(self._nyuki, token) or {}
        log.info('Sending ready packet')
        log.debug('ready dump: %s', ready)
        await websocket.send(json.dumps(ready, default=self._serializer))

    def _check_token_usage(self, token):
        """
        Delete token if never used
        """
        if token in self.clients and self.clients[token] is None:
            log.debug("token '%s' never used, deleting it", token)
            del self.clients[token]

    async def _end_websocket_client(self, websocket, token, reason):
        """
        Close the connection if no keepalive have been received
        """
        if self.CLOSE_CALLBACK:
            log.info('Close callback set up, calling it before ending client')
            await self.CLOSE_CALLBACK(self._nyuki, token)
        websocket.close(reason=reason)
        try:
            del self.clients[token]
        except KeyError as ke:
            log.debug("token '%s' already removed from keepalive", ke)

    def _schedule_keepalive(self, websocket, token):
        return self._loop.call_later(
            self.keepalive,
            lambda: asyncio.ensure_future(self._end_websocket_client(
                websocket, token, 'keepalive timed out'
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
        if token not in self.clients:
            log.debug("Unknown token '%s'", token)
            websocket.close()
            return
        elif self.clients[token] is not None:
            log.debug("Token already in use: '%s'", token)
            websocket.close()
            return

        log.info('Connection from token: %s', token)
        handle = self._schedule_keepalive(websocket, token)
        await self._send_ready(websocket, token)

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
                handle = self._schedule_keepalive(websocket, token)

        handle.cancel()
        await self._end_websocket_client(
            websocket, token, 'connection closed normally'
        )
