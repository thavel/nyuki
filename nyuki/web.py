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


def websocket_resource(ws_type):
    def decorated(func):
        if not asyncio.iscoroutine(func):
            func = asyncio.coroutine(func)
        WebHandler.RESOURCES[ws_type] = func
        return func
    return decorated


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

    RESOURCES = {}
    MESSAGE_SCHEMA = {
        'type': 'object',
        'required': ['type'],
        'properties': {
            'type': {
                'type': 'string',
                'minLength': 1
            },
            'id': {'type': 'integer'},
            'data': {'type': 'object'}
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
        Random token using 20 digits/lowercases
        """
        token = ''.join(
            random.choice(string.ascii_letters + string.digits)
            for _ in range(30)
        )
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
            'keepalive_delay': self.keepalive,
            'data': {}
        }
        if 'ready' in self.RESOURCES:
            log.info('ready resource found, calling it for new client')
            ready['data'] = await self.RESOURCES['ready'](self._nyuki) or {}
        log.info('Sending ready packet')
        log.debug('ready dump: %s', ready)
        await websocket.send(json.dumps(ready))

    def keepalive_timeout(self, websocket):
        """
        Close the connection if no keepalive have been received
        """
        asyncio.ensure_future(websocket.close(reason='keepalive timed out'))

    async def _wshandler(self, websocket, path):
        """
        Main handler for a newly connected client
        """
        # match = re.match(r'^\/(?P<token>[a-zA-Z0-9]{30})$', path)
        # if not match:
        #     websocket.close()
        #     return

        # token = match.group('token')
        # if token not in self._tokens:
        #     log.debug("Unknown token '%s'", token)
        #     websocket.close()
        #     return

        handle = self._loop.call_later(
            self.keepalive, self.keepalive_timeout, websocket
        )
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
                log.debug("Message '{}' is not JSON".format(message))
                continue

            try:
                validate(data, self.MESSAGE_SCHEMA)
            except ValidationError:
                log.debug("Invalid data '{}' received".format(data))
                continue

            resource = data['type']
            if resource == 'keepalive':
                handle.cancel()
                handle = self._loop.call_later(
                    self.keepalive, self.keepalive_timeout, websocket
                )

            if resource not in self.RESOURCES:
                log.warning("Resource '{}' unknown".format(resource))
                continue

            log.info("Websocket message for resource '{}'".format(resource))
            response = await self.RESOURCES[resource](
                self._nyuki, data.get('data', {})
            )

            # XXX Should we handle websocket requests ? or only http ?
            if response:
                await websocket.send(json.dumps({
                    'id': data['id'],
                    'data': response
                }))

        websocket.close()
        handle.cancel()
