from aiohttp import web
from aiohttp.hdrs import METH_ALL
import asyncio
from functools import partial
import json
import logging

from nyuki.bus import reporting
from nyuki.services import Service


log = logging.getLogger(__name__)
# aiohttp needs its own logger, and always prints HTTP hits using INFO level
access_log = logging.getLogger('.'.join([__name__, 'access']))
access_log.info = access_log.debug


class Response(web.Response):

    """
    Overrides aiohttp's response to facilitate its usage
    """

    ENCODING = 'utf-8'

    def __init__(self, body=None, **kwargs):

        # Check json
        if isinstance(body, dict) or isinstance(body, list):
            log.debug('converting dict/list response to bytes')
            body = json.dumps(body).encode(self.ENCODING)
            if not self._get_content_type(kwargs):
                kwargs['content_type'] = 'application/json'
        # Check body
        elif body is not None:
            log.debug('converting string response to bytes')
            body = str(body).encode(self.ENCODING)
            if not self._get_content_type(kwargs):
                kwargs['content_type'] = 'text/plain'

        return super().__init__(body=body, **kwargs)

    def _get_content_type(self, kwargs):
        return kwargs.get('content_type') or kwargs.get('headers', {}).get('content_type')


class WebServer:

    """
    The goal of this class is to gather all http-related behaviours.
    Basically, it's a wrapper around aiohttp.
    """

    def __init__(self, loop, debug=False, **kwargs):
        self._loop = loop
        self._server = None
        self._handler = None
        # Call order = list order
        self._middlewares = [mw_capability]
        self._debug = debug
        self._app = web.Application(
            loop=self._loop,
            middlewares=self._middlewares,
            **kwargs
        )

    @property
    def debug(self):
        return self._debug

    @debug.setter
    def debug(self, value):
        self._debug = bool(value)

    @property
    def router(self):
        return self._app.router

    async def build(self, host, port):
        """
        Create a HTTP server to expose the API.
        """
        log.info("Starting the http server on {}:{}".format(host, port))
        self._handler = self._app.make_handler(
            log=log, access_log=access_log, debug=self._debug
        )
        self._server = await self._loop.create_server(
            self._handler, host=host, port=port
        )

    async def destroy(self):
        """
        Gracefully destroy the HTTP server by closing all pending connections.
        """
        self._server.close()
        await self._handler.finish_connections()
        await self._server.wait_closed()
        log.info('Stopped the http server')


async def mw_capability(app, capa_handler):
    """
    Transform the request data to be passed through a capability and
    convert the result into a web response.
    """
    async def middleware(request):
        # Ensure a content-type check is necessary
        if getattr(capa_handler, 'CONTENT_TYPE', None) and await request.text():
            ctype = capa_handler.CONTENT_TYPE

            # Check content_type from @resource decorator
            if request.headers.get('Content-Type') != ctype:
                log.debug(
                    "content-type '%s' required. Received '%s'",
                    ctype,
                    request.headers.get('Content-Type')
                )
                return Response(
                    {'error': 'Wrong content-type'},
                    status=400
                )

            # Check application/json is really a JSON body
            if ctype == 'application/json':
                try:
                    await request.json()
                except json.decoder.JSONDecodeError:
                    log.debug('request body for application/json must be JSON')
                    return Response(
                        {'error': 'application/json requires a JSON body'},
                        status=400
                    )

        try:
            capa_resp = await capa_handler(request, **request.match_info)
        except (web.HTTPNotFound, web.HTTPMethodNotAllowed):
            # Avoid sending a report on a simple 404/405
            raise
        except Exception as exc:
            reporting.exception(exc)
            raise exc

        if capa_resp and isinstance(capa_resp, Response):
            return capa_resp

        return Response()

    return middleware


def resource(path, versions=None, content_type=None):
    """
    Nyuki resource decorator to register a route.
    A resource has multiple HTTP methods (get, post, etc).
    """
    def decorated(cls):
        cls.RESOURCE_CLASS = ResourceClass(cls, path, versions, content_type)
        return cls
    return decorated


class ResourceClass:

    """
    Allow the extensivity of the nyuki's HTTP resources using the webserver's
    router from the `Api` class.
    """

    def __init__(self, cls, path, versions, content_type):
        self.cls = cls
        self.path = path
        self.versions = versions
        self.content_type = content_type

    def _add_routes(self, router, path):
        resource = router.add_resource(path)
        cls_instance = self.cls()
        for method in METH_ALL:
            handler = getattr(self.cls, method.lower(), None)
            if handler is not None:
                handler = asyncio.coroutine(partial(handler, cls_instance))
                handler.CONTENT_TYPE = self.content_type
                route = resource.add_route(method, handler)
                log.debug('Added route: %s', route)

    def register(self, nyuki, router):
        self.cls.nyuki = nyuki
        if not self.versions:
            self._add_routes(router, self.path)
        else:
            for version in self.versions:
                route = '/{}{}'.format(version, self.path)
                self._add_routes(router, route)


class Api(Service):

    """
    Manage a webserver built using the nyuki's defined HTTP resources
    """

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
        self._webserver = WebServer(self._loop)
        self.host = None
        self.port = None

    @property
    def capabilities(self):
        return self._nyuki.HTTP_RESOURCES

    async def start(self):
        """
        Expose capabilities by building the HTTP server.
        The server will be started with the event loop.
        """
        for resource in self._nyuki.HTTP_RESOURCES:
            resource.RESOURCE_CLASS.register(self._nyuki, self._webserver.router)
        await self._webserver.build(self.host, self.port)

    def configure(self, host='0.0.0.0', port=5558, debug=False):
        self.host = host
        self.port = port
        self._webserver.debug = debug

    async def stop(self):
        await self._webserver.destroy()
