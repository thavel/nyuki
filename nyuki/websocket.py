import asyncio
import json
import logging
import websockets
from jsonschema import validate, ValidationError

from nyuki.services import Service
from nyuki.utils import serialize_object


log = logging.getLogger(__name__)


class WebsocketResource:

    # Value before the client is timed out after not sending any keepalive.
    KEEPALIVE = 60

    def __init__(self, path):
        self._clients = []
        self._path = path
        log.info("New websocket resource on path: '%s'", path)
        WebsocketHandler.RESOURCES[path] = self

    def end(self):
        """
        Unregister this resource, the object becoming stall.
        """
        asyncio.ensure_future(self.close_clients())
        log.info("Ended websocket resource on path: '%s'", self._path)
        del WebsocketHandler.RESOURCES[self._path]

    async def close_clients(self):
        log.debug("Closing all websocket connections on path: '%s'", self._path)
        tasks = [
            asyncio.ensure_future(self.remove_client(client, 1001, 'server closing'))
            for client in self._clients
        ]
        if tasks:
            await asyncio.wait(tasks)
        self._clients = []

    async def add_client(self, client):
        ready = {
            'type': 'ready',
            'keepalive_delay': self.KEEPALIVE,
            'data': await self.ready(client) or {}
        }
        await client.send(json.dumps(ready, default=serialize_object))
        self._clients.append(client)

    async def remove_client(self, client, code=None, reason=None):
        if client not in self._clients:
            return
        if code is None:
            code = 1000
        if reason is None:
            reason = 'connection closed normally'
        await self.close(client)
        await client.close(code, reason)
        if client in self._clients:
            self._clients.remove(client)

    async def broadcast(self, data, timeout=None):
        """
        Send a message to every connected client.
        """
        if not self._clients:
            return
        if not isinstance(data, str):
            data = json.dumps(data, default=serialize_object)

        tasks = [
            asyncio.ensure_future(client.send(data))
            for client in self._clients
        ]
        log.debug(
            'Sending data of length %s to %s clients',
            len(data), len(self._clients)
        )
        await asyncio.wait(tasks, timeout=timeout)

    async def ready(self, client):
        """
        Called on a new client connection.
        """

    async def close(self, client):
        """
        Called on a client disconnection.
        """


class WebsocketHandler(Service):

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

    RESOURCES = {}
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

    async def start(self):
        """
        Start the websocket server
        """
        log.info("Starting websocket server on %s:%s", self.host, self.port)
        self.server = await websockets.serve(
            self._wshandler, self.host, self.port
        )

    def configure(self, host='0.0.0.0', port=5559):
        self.host = host
        self.port = port

    async def stop(self):
        if not self.server:
            return
        for resource in self.RESOURCES.values():
            asyncio.ensure_future(resource.close_clients())
        self.server.close()
        await self.server.wait_closed()

    def _schedule_keepalive(self, resource, client):
        def timeout():
            asyncio.ensure_future(resource.remove_client(
                client, 4008, 'keepalive timed out'
            ))
        return self._loop.call_later(resource.KEEPALIVE, timeout)

    async def _wshandler(self, websocket, path):
        """
        Main handler for a newly connected client
        """
        try:
            resource = self.RESOURCES[path]
        except KeyError:
            await websocket.close(4004, 'resource not found')
            return

        await resource.add_client(websocket)
        handle = self._schedule_keepalive(resource, websocket)

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
                handle = self._schedule_keepalive(resource, websocket)

        # 'websocket' client may already be closed here.
        handle.cancel()
        await resource.remove_client(websocket)
