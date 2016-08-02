from aiohttp.hdrs import METH_ALL
import asyncio
from functools import partial
import logging

from nyuki.services import Service

from .webserver import WebServer


log = logging.getLogger(__name__)


def resource(endpoint, versions=None, content_type=None):
    """
    Nyuki resource decorator to register a route.
    A resource has multiple HTTP methods (get, post, etc).
    """
    def decorated(cls):
        cls.RESOURCE_CLASS = ResourceClass(cls, endpoint, versions, content_type)
        return cls
    return decorated


class ResourceClass:

    def __init__(self, cls, route, versions, content_type):
        self.cls = cls
        self.route = route
        self.versions = versions
        self.content_type = content_type

    def _add_route(self, router, route):
        resource = router.add_resource(route)
        for method in METH_ALL:
            handler = getattr(self.cls, method.lower(), None)
            if handler is not None:
                handler.CONTENT_TYPE = self.content_type
                # Automatically switched to a coroutine inside the router
                route = resource.add_route(method, partial(handler, self.cls()))
                log.debug('Added route: %s', route)

    def register(self, nyuki, router):
        self.cls.nyuki = nyuki
        if not self.versions:
            self._add_route(router, self.route)
        else:
            for version in self.versions:
                route = '/{}{}'.format(version, self.route)
                self._add_route(router, route)


class Api(Service):

    CONF_SCHEMA = {
        "type": "object",
        "required": ["api"],
        "properties": {
            "api": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"}
                }
            }
        }
    }

    def __init__(self, nyuki):
        self._nyuki = nyuki
        self._nyuki.register_schema(self.CONF_SCHEMA)
        self._loop = self._nyuki.loop or asyncio.get_event_loop()
        self._api = WebServer(self._loop)
        self.host = None
        self.port = None

    @property
    def capabilities(self):
        return self.ENDPOINTS

    async def start(self):
        """
        Expose capabilities by building the HTTP server.
        The server will be started with the event loop.
        """
        for endpoint in self._nyuki.ENDPOINTS:
            endpoint.RESOURCE_CLASS.register(self._nyuki, self._api.router)
        await self._api.build(self.host, self.port)

    def configure(self, host='0.0.0.0', port=5558, debug=False):
        self.host = host
        self.port = port
        self._api.debug = debug

    async def stop(self):
        await self._api.destroy()
