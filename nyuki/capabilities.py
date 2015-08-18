import logging
import asyncio

from nyuki.api import Api


log = logging.getLogger(__name__)


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


class Exposer(object):
    """
    Provide a engine to expose nyuki capabilities through a HTTP API.
    """
    def __init__(self, loop):
        self._loop = loop
        self._capabilities = set()
        self._api = Api(loop)
        log.debug("Capabilities will be called through {}".format(loop))

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
        Expose capabilities by building the HTTP server.
        The server will be started with the event loop.
        """
        log.debug("Starting the http server on {}:{}".format(host, port))
        self._loop.run_until_complete(self._api.build(host, port))

    def shutdown(self):
        """
        Shutdown capabilities exposure by destroying the HTTP server.
        """
        log.debug("Stopping the http server")
        asyncio.async(self._api.destroy(), loop=self._loop)
