from aiohttp import web, HttpBadRequest
from enum import Enum
import logging


log = logging.getLogger(__name__)
# aiohttp needs its own logger, and always prints HTTP hits using INFO level
access_log = logging.getLogger('.'.join([__name__, 'access']))
access_log.info = access_log.debug


class Method(Enum):

    """
    Supported HTTP methods by the REST API.
    """

    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'
    HEAD = 'HEAD'
    OPTIONS = 'OPTIONS'
    TRACE = 'TRACE'
    CONNECT = 'CONNECT'
    PATCH = 'PATCH'

    @classmethod
    def list(cls):
        return [method.name for method in cls]


class Api(object):

    """
    The goal of this class is to gather all http-related behaviours.
    Basically, it's a wrapper around aiohttp.
    """

    def __init__(self, loop, debug=False, **kwargs):
        self._loop = loop
        self._server = None
        self._handler = None
        self._middlewares = [mw_json, mw_capability]  # Call order = list order
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


async def mw_json(app, next_handler):
    """
    Ensure the content type is `application/json` for all POST-like requests.
    """
    async def middleware(request):
        if request.method in request.POST_METHODS:
            content_type = request.headers.get('CONTENT-TYPE')
            if content_type:
                if 'application/json' in content_type:
                    # Checking that the content is actually JSON
                    # there could be a charset specified.
                    try:
                        await request.json()
                    except ValueError:
                        log.error('Invalid JSON request content')
                        raise HttpBadRequest('Invalid JSON request content')
                elif 'application/xml' in content_type:
                    # xml is often user for preflight CORS requests
                    # so, let's the user implement a middleware to handle it
                    pass
                elif 'text/' in content_type:
                    pass
                else:
                    log.error('Invalid Content-Type')
                    raise HttpBadRequest('Invalid Content-Type')
            elif (await request.content.read()):
                log.error('Missing suitable Content-Type')
                raise HttpBadRequest('Missing suitable Content-Type')
        response = await next_handler(request)
        return response
    return middleware


class APIRequest(dict):
    """
    Class that stores the request data and the headers as an attribute.
    """

    headers = None

    @classmethod
    async def from_request(cls, request):
        # Get json payload if there is one
        if request.method in request.POST_METHODS:
            try:
                data = await request.json()
            except ValueError:
                data = None
        else:
            data = dict(getattr(request, request.method, {}))

        # Set up class and headers as request attribute
        req = cls(**data) if data else cls()
        req.raw = await request.text()
        req.headers = request.headers
        req.raw_path = request.raw_path
        return req


async def mw_capability(app, capa_handler):
    """
    Transform the request data to be passed through a capability and
    convert the result into a web response.
    From here, we are expecting a JSON content.
    """
    async def middleware(request):
        api_req = await APIRequest.from_request(request)

        try:
            capa_resp = await capa_handler(api_req, **request.match_info)
        except web.HTTPNotFound:
            # Avoid sending a report on a simple 404 Not Found
            raise
        except Exception as exc:
            # Access private '_exception_handler' attribute to avoid calling
            # the 'default_exception_handler' a second time if no exception
            # handler has been set on our side (no bus)
            if app.loop._exception_handler:
                app.loop.call_exception_handler({
                    'message': str(exc),
                    'exception': exc
                })
            raise exc

        if capa_resp and isinstance(capa_resp, web.Response):
            return capa_resp
        else:
            return web.Response()

    return middleware
