import json
import logging
import asyncio

from nyuki.api import Api


log = logging.getLogger(__name__)


def resource(endpoint, version=None):
    """
    Nyuki resource decorator to register a route.
    A resource has multiple HTTP methods (get, post, etc).
    """
    def decorated(cls):
        cls.endpoint = endpoint
        cls.version = version
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


class Response(object):
    """
    This class is a generic response (with a body and a status) that can be
    used by either the bus or the API.
    """
    ENCODING = 'utf-8'

    def __init__(self, body=None, status=200):
        self.body = body or dict()
        self.status = status
        self._is_valid()

    def _is_valid(self):
        if not isinstance(self.body, dict) and not isinstance(self.body, list):
            raise ValueError("Response body should be a dictionary or a list")
        if not isinstance(self.status, int):
            raise ValueError("Response status code should be a integer")

    @property
    def api_payload(self):
        """
        Used by the HTTP API.
        """
        self._is_valid()
        payload = json.dumps(self.body)
        return bytes(payload, self.ENCODING)


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

    def expose(self, host='0.0.0.0', port=8080):
        """
        Expose capabilities by building the HTTP server.
        The server will be started with the event loop.
        """
        self._loop.run_until_complete(self._api.build(host, port))

    def restart(self, host='0.0.0.0', port=8080):
        """
        Restart the HTTP server.
        """
        # Stopping the API server
        fut = self.shutdown()
        # Rebuilding the API server afterwards
        fut.add_done_callback(
            lambda x: asyncio.async(self._api.build(host, port)))

    def shutdown(self):
        """
        Shutdown capabilities exposure by destroying the HTTP server.
        """
        log.debug("Stopping the http server")
        return asyncio.async(self._api.destroy(), loop=self._loop)

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
        future = asyncio.async(capa.wrapper(request), loop=self._loop)
        return future
