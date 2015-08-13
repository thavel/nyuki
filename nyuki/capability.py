import logging
from collections import namedtuple

from aiohttp import web


log = logging.getLogger(__name__)


Capability = namedtuple('Capability', ['name', 'method', 'access', 'endpoint'])


class CapabilityExposer(object):
    """
    Provide a engine to expose nyuki capabilities through a HTTP API.
    """
    def __init__(self, loop):
        self._loop = loop.loop
        self._capabilities = set()
        self._app = web.Application(loop=self._loop)
        log.debug("Capabilities will be called through {}".format(self._loop))

    @property
    def capabilities(self):
        return self._capabilities

    def register(self, capa):
        """
        Add a capability and its HTTP route.
        """
        self._capabilities.add(capa)
        self._app.router.add_route(capa.access, capa.endpoint, capa.method)
        log.debug("Capability added: {}".format(capa.name))

    def find(self, capa_name):
        """
        Get a capability by its name.
        """
        for capability in self._capabilities:
            if capa_name == capability.name:
                return capability

    def use(self, name, *args):
        """
        Call a capability by its name in an asynchronous fashion.
        """
        capa = self.find(name)
        if not capa:
            log.warning("Capability {} is called but doen't exist".format(name))
        self._loop.call_soon(capa.method, *args)

    def _build_http(self, host, port):
        """
        Create a HTTP server to expose the API.
        """
        future = yield from self._loop.create_server(
            self._app.make_handler(log=log, access_log=log),
            host=host, port=port
        )
        return future

    def expose(self, host='0.0.0.0', port=8080):
        """
        Init the HTTP server.
        """
        log.debug("Starting the http server on {}:{}".format(host, port))
        self._loop.run_until_complete(self._build_http(host, port))


class Response(web.Response):
    """
    Provide a wrapper around aiohttp to ease HTTP responses.
    """
    ENCODING = 'utf-8'

    def __init__(self, body, **kwargs):
        if isinstance(body, str):
            body = bytes(body, self.ENCODING)
        super().__init__(body=body, **kwargs)
