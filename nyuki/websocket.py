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
    async def decorated(self):
        return await func(self)

    WebHandler.READY_CALLBACK = decorated
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
        self._tokens = []

    async def start(self):
        """
        Start the websocket server
        """
        log.info("Starting websocket server on %s:%s", self.host, self.port)
        self.server = await websockets.serve(
            self._wshandler, self.host, self.port
        )

    def configure(self, host='0.0.0.0', port=5559, keepalive=600):
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
        self._tokens.append(token)
        return token

    async def broadcast(self, message):
        """
        Send a message to every connected client
        """
        data = json.dumps(message)
        log.debug('Sending {} to all WS clients'.format(data))
        for websocket in self.server.websockets:
            await websocket.send(data)

    async def send_ready(self, websocket):
        """
        Send the 'ready' message to a client
        """
        ready = {
            'type': 'ready',
            'keepalive_delay': self.keepalive * 0.8,
            'data': {}
        }
        if self.READY_CALLBACK:
            log.info('Ready callback set up, calling it for new client')
            ready['data'] = await self.READY_CALLBACK(self._nyuki) or {}
        log.info('Sending ready packet')
        log.debug('ready dump: %s', ready)
        await websocket.send(json.dumps(ready))

    def _end_websocket_client(self, websocket, token, reason):
        """
        Close the connection if no keepalive have been received
        """
        websocket.close(reason=reason)
        try:
            self._tokens.remove(token)
        except ValueError:
            log.debug('token already removed from keepalive')

    def _schedule_keepalive(self, websocket, token):
        return self._loop.call_later(
            self.keepalive,
            self._end_websocket_client,
            websocket,
            token,
            'keepalive timed out'
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
        if token not in self._tokens:
            log.debug("Unknown token '%s'", token)
            websocket.close()
            return

        log.info('Connection from token: %s', token)
        handle = self._schedule_keepalive(websocket, token)
        await self.send_ready(websocket)

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
        self._end_websocket_client(websocket, token, 'connection closed normally')
