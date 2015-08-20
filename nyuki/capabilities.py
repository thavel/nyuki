import json
import logging
import asyncio

from nyuki.events import Event, on_event
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


def capability(name=None):
    """
    Nyuki resource method decorator to register a capability.
    It will be exposed as a HTTP route for the nyuki's API.
    """
    def decorated(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper.capability = name
        return wrapper
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
    ENCODING = 'utf-8'

    def __init__(self, body=None, status=200):
        self.body = body or dict()
        self.status = status
        self._is_valid()

    def _is_valid(self):
        if not isinstance(self.body, dict):
            raise ValueError("Response body should be a dictionary")
        if not isinstance(self.status, int):
            raise ValueError("Response status code should be a integer")

    @property
    def api_payload(self):
        self._is_valid()
        payload = json.dumps(self.body)
        return bytes(payload, self.ENCODING)

    @property
    def bus_message(self):
        self._is_valid()
        self.body.update({'status': self.status})
        return self.body


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
        log.debug("Starting the http server on {}:{}".format(host, port))
        self._loop.run_until_complete(self._api.build(host, port))

    def shutdown(self):
        """
        Shutdown capabilities exposure by destroying the HTTP server.
        """
        log.debug("Stopping the http server")
        asyncio.async(self._api.destroy(), loop=self._loop)

    def _find(self, capa_name):
        """
        Get a capability by its name.
        """
        for capability in self._capabilities:
            if capa_name == capability.name:
                return capability

    def _call(self, name, request):
        """
        Call a capability by its name in an asynchronous fashion.
        """
        capa = self._find(name)
        if not capa:
            log.warning("Capability {} is called but doen't exist".format(name))

        # TODO: use asyncio.ensure_future when Python 3.4.4 will be released
        future = asyncio.async(capa.wrapper(request), loop=self._loop)
        return future

    @on_event(Event.RequestReceived)
    def _handle_request(self, event):
        """
        Handle request received from the bus.
        Call the targeted capability.
        """
        capa_name, request, response_callback = event
        future = self._call(capa_name, request)
        future.add_done_callback(response_callback)

    @on_event(Event.ResponseReceived)
    def _handle_response(self, response):
        """
        Handle response for a request sent through the bus.
        """
        log.debug("Response received, but ignored")
