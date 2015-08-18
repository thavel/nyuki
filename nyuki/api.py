import logging
import asyncio
from enum import Enum

from aiohttp import web


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
        self._app = web.Application(loop=self._loop, **kwargs)
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


class Response(web.Response):
    """
    Provide a wrapper around aiohttp to ease HTTP responses.
    """
    ENCODING = 'utf-8'

    def __init__(self, body, **kwargs):
        if isinstance(body, str):
            body = bytes(body, self.ENCODING)
        super().__init__(body=body, **kwargs)
