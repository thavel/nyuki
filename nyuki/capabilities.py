import asyncio
import logging

from nyuki.api import Api
from nyuki.services import Service


log = logging.getLogger(__name__)


def resource(endpoint, version=None, content_type=None):
    """
    Nyuki resource decorator to register a route.
    A resource has multiple HTTP methods (get, post, etc).
    """
    def decorated(cls):
        cls.endpoint = endpoint
        cls.version = version
        cls.content_type = content_type or 'application/json'
        return cls
    return decorated


class Capability(object):

    """
    A capability is unique (hashable object, based on capability's name).
    """

    def __init__(self, name, method, endpoint, version, handler, wrapper):
        self.name = name
        self.method = method
        self.endpoint = endpoint
        self.version = version
        self.handler = handler
        self.wrapper = wrapper

    def __hash__(self):
        return hash(self.name)


class Exposer(Service):

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
        self._capabilities = set()
        self._api = Api(self._loop)
        self.host = None
        self.port = None

    async def start(self):
        """
        Expose capabilities by building the HTTP server.
        The server will be started with the event loop.
        """
        await self._api.build(self.host, self.port)

    def configure(self, host='0.0.0.0', port=5558, debug=False):
        self.host = host
        self.port = port
        self._api.debug = debug

    async def stop(self):
        await self._api.destroy()

    @property
    def capabilities(self):
        return self._capabilities

    def register(self, capa):
        """
        Add a capability and register its route to the API.
        """
        if capa in self._capabilities:
            raise ValueError("A capability is already exposed through {} with "
                             "{} method".format(capa.endpoint, capa.method))
        self._capabilities.add(capa)
        # Handle version as part of the endpoint (if defined)
        if capa.version:
            endpoint = '/{}{}'.format(capa.version, capa.endpoint)
        else:
            endpoint = capa.endpoint
        self._api.router.add_route(capa.method, endpoint, capa.wrapper)
        log.debug("Capability added: {}".format(capa.name))

    def _find(self, capa_name):
        """
        Get a capability by its name.
        """
        for capability in self._capabilities:
            if capa_name == capability.name:
                return capability

    def call(self, name, request):
        """
        Call a capability by its name in an asynchronous fashion.
        """
        capa = self._find(name)
        if not capa:
            log.warning("Capability {} is called but doen't exist".format(name))
            return

        # TODO: use asyncio.ensure_future when Python 3.4.4 will be released
        future = asyncio.ensure_future(capa.wrapper(request), loop=self._loop)
        return future
