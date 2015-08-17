import logging
import asyncio

from aiohttp import web


log = logging.getLogger(__name__)


class Capability(object):
    """
    A capability is unique (hashable object, based on capability's name).
    """
    def __init__(self, name, handler, method, endpoint):
        self.name = name
        self.handler = handler
        self.method = method.upper()
        self.endpoint = endpoint

    def __hash__(self):
        return hash(self.method) + hash(self.endpoint)


class _HttpApi(object):
    """
    The goal of this class is to gather all http-related behaviours.
    """
    def __init__(self, loop):
        self._loop = loop
        self._app = web.Application(loop=self._loop)
        self._server = None
        self._handler = None

    @property
    def router(self):
        return self._app.router

    @asyncio.coroutine
    def build(self, host, port):
        """
        Create a HTTP server to expose the API.
        """
        self._handler = self._app.make_handler(log=log, access_log=log)
        self._server = yield from self._loop.create_server(self._handler,
                                                           host=host, port=port)

    @asyncio.coroutine
    def destroy(self):
        """
        Gracefully destroy the HTTP server by closing all pending connections.
        """
        self._server.close()
        yield from self._handler.finish_connections()
        yield from self._server.wait_closed()


class CapabilityExposer(object):
    """
    Provide a engine to expose nyuki capabilities through a HTTP API.
    """
    def __init__(self, loop):
        self._loop = loop
        self._capabilities = set()
        self._api = _HttpApi(loop)
        log.debug("Capabilities will be called through {}".format(loop))

    @property
    def capabilities(self):
        return self._capabilities

    def register(self, capa):
        """
        Add a capability and its HTTP route.
        """
        if capa in self._capabilities:
            raise ValueError("A capability is already exposed through {} with "
                             "{} method".format(capa.endpoint, capa.method))
        self._capabilities.add(capa)
        self._api.router.add_route(capa.method, capa.endpoint, capa.handler)
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
        self._loop.call_soon(capa.handler, *args)

    def expose(self, host='0.0.0.0', port=8080):
        """
        Init the HTTP server.
        """
        log.debug("Starting the http server on {}:{}".format(host, port))
        self._loop.run_until_complete(self._api.build(host, port))

    def shutdown(self):
        """
        Destroy the HTTP server.
        """
        log.debug("Stopping the http server")
        asyncio.async(self._api.destroy(), loop=self._loop)


class Response(web.Response):
    """
    Provide a wrapper around aiohttp to ease HTTP responses.
    """
    ENCODING = 'utf-8'

    def __init__(self, body, **kwargs):
        if isinstance(body, str):
            body = bytes(body, self.ENCODING)
        super().__init__(body=body, **kwargs)
