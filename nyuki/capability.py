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

    def _build_http(self, host, port):
        """
        Create a HTTP server to expose the API.
        """
        future = yield from self._loop.create_server(
            self._app.make_handler(log=log, access_log=log),
            host=host, port=port
        )
        return future

    def expose(self, host, port):
        """
        Init the HTTP server.
        """
        log.debug("Starting the http server")
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
