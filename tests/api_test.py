from aiohttp import web
from asynctest import TestCase, Mock, patch, ignore_loop
from json import loads
from nose.tools import (
    assert_is, assert_is_not_none, assert_raises, assert_true, eq_
)

from nyuki.api import Api, mw_capability, Response
from tests import make_future


class TestApi(TestCase):

    def setUp(self):
        self._api = Api(self.loop)
        self._host = 'localhost'
        self._port = 8080

    @patch('aiohttp.web.Application.make_handler')
    @patch('asyncio.unix_events._UnixSelectorEventLoop.create_server')
    async def test_001_build_server(self, create_server_mock, handler_mock):
        await self._api.build(self._host, self._port)
        eq_(handler_mock.call_count, 1)
        eq_(create_server_mock.call_count, 1)
        create_server_mock.assert_called_with(
            self._api._handler, host=self._host, port=self._port
        )

    async def test_002_destroy_server(self):
        with patch.object(self._api, '_handler') as i_handler:
            i_handler.finish_connections.return_value = make_future([])
            with patch.object(self._api, '_server') as i_server:
                i_server.wait_closed.return_value = make_future([])
                with patch.object(self._api._server, 'close') as call_close:
                    await self._api.destroy()
                    eq_(call_close.call_count, 1)
                    eq_(i_server.wait_closed.call_count, 1)

    @ignore_loop
    def test_003_instantiated_router(self):
        assert_is(self._api.router, self._api._app.router)


class TestCapabilityMiddleware(TestCase):

    def setUp(self):
        self._request = Mock()
        self._request.POST_METHODS = ['POST', 'PUT', 'PATCH']
        self._app = Mock()
        async def json():
            return {'capability': 'test'}
        async def text():
            return '{"capability": "test"}'
        self._request.json = json
        self._request.text = text

    async def test_001a_extract_data_from_payload_post_method(self):
        self._request.method = 'POST'
        self._request.match_info = {'name': 'test'}

        async def _capa_handler(d, name):
            eq_(name, 'test')
            capa_resp = Response({'response': 'ok'})
            return capa_resp

        mdw = await mw_capability(self._app, _capa_handler)
        assert_is_not_none(mdw)
        response = await mdw(self._request)
        assert_true(isinstance(response, web.Response))
        eq_(loads(response.body.decode('utf-8'))["response"], 'ok')
        eq_(response.status, 200)

    async def test_001b_extract_data_from_non_post_method(self):
        self._request.method = 'GET'
        self._request.GET = {'id': 2}
        self._request.match_info = {'name': 'test'}

        async def _capa_handler(d, name):
            eq_(name, 'test')
            capa_resp = Response({'response': 2})
            return capa_resp

        mdw = await mw_capability(self._app, _capa_handler)
        assert_is_not_none(mdw)
        response = await mdw(self._request)
        assert_true(isinstance(response, web.Response))
        eq_(loads(response.body.decode('utf-8'))["response"], 2)
        eq_(response.status, 200)

    async def test_001c_post_no_data(self):
        self._request.method = 'POST'
        self._request.match_info = {'name': 'test'}

        async def _capa_handler(d, name):
            eq_(name, 'test')
            capa_resp = Response({'response': 'ok'})
            return capa_resp

        mdw = await mw_capability(self._app, _capa_handler)
        assert_is_not_none(mdw)
        response = await mdw(self._request)
        assert_true(isinstance(response, web.Response))
        eq_(loads(response.body.decode('utf-8'))["response"], 'ok')
        eq_(response.status, 200)

    async def test_002_no_response(self):
        self._request.method = 'GET'
        self._request.GET = {}
        self._request.match_info = {}

        async def _capa_handler(d):
            return Response()

        mdw = await mw_capability(self._app, _capa_handler)
        assert_is_not_none(mdw)
        response = await mdw(self._request)
        assert_true(isinstance(response, web.Response))
        eq_(response.body, None)
        eq_(response.status, 200)

    async def test_003_request_headers(self):
        self._request.method = 'POST'
        self._request.match_info = {'name': 'test'}
        self._request.headers = {'Content-Type': 'application/json'}

        ar = await self._request.json()
        eq_(ar['capability'], 'test')
        eq_(self._request.headers.get('Content-Type'), 'application/json')

    async def test_004_exception(self):
        self._request.method = 'GET'
        self._request.GET = {}
        self._request.match_info = {}

        exc = Exception('fail')
        async def _capa_handler(d):
            raise exc

        mdw = await mw_capability(self._app, _capa_handler)
        assert_is_not_none(mdw)

        with patch.object(self._app.loop, 'call_exception_handler') as exc_handler:
            with assert_raises(Exception):
                await mdw(self._request)
            exc_handler.assert_called_once_with({
                'message': str(exc),
                'exception': exc
            })
