from aiohttp import web
from enum import Enum
import json
import logging

from nyuki.bus import reporting


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


class Api(object):

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

        if request.method in request.POST_METHODS and hasattr(capa_handler, 'CONTENT_TYPE'):
            ctype = capa_handler.CONTENT_TYPE

            # Check content_type from @resource decorator
            if request.headers.get('Content-Type') != ctype:
                log.debug("content-type '%s' required", ctype)
                return Response(
                    {'error': 'Wrong content-type'},
                    status=400
                )

            # Check application/json is really a JSON body
            if ctype == 'application/json':
                try:
                    await request.json()
                except json.decoder.JSONDecodeError:
                    log.debug("request body for application/json must be JSON")
                    return Response(
                        {'error': 'application/json requires a JSON body'},
                        status=400
                    )

        try:
            capa_resp = await capa_handler(request, **request.match_info)
        except web.HTTPNotFound:
            # Avoid sending a report on a simple 404 Not Found
            raise
        except Exception as exc:
            reporting.exception(exc)
            raise exc

        if capa_resp and isinstance(capa_resp, Response):
            return capa_resp

        return Response()

    return middleware
