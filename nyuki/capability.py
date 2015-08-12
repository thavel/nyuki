import logging
from aiohttp import web


log = logging.getLogger(__name__)


class Capability(object):
    def __init__(self, name, method, access, endpoint):
        self.name = name
        self.method = method
        self.access = access
        self.endpoint = endpoint

    def __eq__(self, other):
        return self.method == other.method

class CapabilityExposer(object):
    def __init__(self, loop):
        self._loop = loop.loop
        self._capabilities = set()
        self._app = web.Application(loop=self._loop)

    @property
    def capabilities(self):
        return self._capabilities

    def register(self, capa):
        self._capabilities.add(capa)
        self._app.router.add_route(capa.accesss, capa.endpoint, capa.method)

    def _start_http(self, host, port):
        future = yield from self._loop.create_server(
            self._app.make_handler(log=log, access_log=log),
            host=host, port=port
        )
        return future

    def expose(self, host, port):
        self._loop.run_until_complete(self._start_http(host, port))
        self._loop.run_forever()
