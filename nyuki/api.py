from aiohttp import web
from aiohttp import HttpBadRequest, BadHttpMessage
import asyncio
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
    def __init__(self, loop, **kwargs):
        self._loop = loop
        self._server = None
        self._handler = None
        self._middlewares = [mw_json, mw_capability]  # Call order = list order
        self._app = web.Application(loop=self._loop,
                                    middlewares=self._middlewares, **kwargs)

    @property
    def router(self):
        return self._app.router

    @asyncio.coroutine
    def build(self, host, port):
        """
        Create a HTTP server to expose the API.
        """
        log.info("Starting the http server on {}:{}".format(host, port))
        self._handler = self._app.make_handler(log=log, access_log=access_log)
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
        log.info('Stopped the http server')


@asyncio.coroutine
def mw_json(app, next_handler):
    """
    Ensure the content type is `application/json` for all POST-like requests.
    """
    @asyncio.coroutine
    def middleware(request):
        if request.method in request.POST_METHODS:
            content_type = request.headers.get('CONTENT-TYPE')
            if not content_type or content_type != 'application/json':
                raise HttpBadRequest('This API only supports JSON content type')
        response = yield from next_handler(request)
        return response
    return middleware


@asyncio.coroutine
def mw_capability(app, capa_handler):
    """
    Transform the request data to be passed through a capability and convert the
    result into a web response.
    From here, we are expecting a JSON content.
    """
    @asyncio.coroutine
    def middleware(request):
        if request.method in request.POST_METHODS:
            try:
                data = yield from request.json()
            except ValueError:
                raise BadHttpMessage('Unvalid JSON request content')
        else:
            data = dict(getattr(request, request.method))
        capa_resp = yield from capa_handler(data)
        headers = {'Content-Type': 'application/json'}
        return web.Response(
            body=capa_resp.api_payload,
            status=capa_resp.status,
            headers=headers)
    return middleware
