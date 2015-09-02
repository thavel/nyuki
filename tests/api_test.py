from aiohttp import errors, web
from json import dumps, loads
from nose.tools import (
    assert_is, assert_is_not_none, assert_raises, assert_true, eq_
)
from tests import AsyncTestCase, fake_future
from unittest.mock import Mock, patch

from nyuki.api import Api, mw_capability, mw_json


class TestApi(AsyncTestCase):

    def setUp(self):
        super().setUp()
        self._api = Api(self._loop)

        self._host = 'localhost'
        self._port = 8080

    @patch('aiohttp.web.Application.make_handler', return_value=True)
    @patch('asyncio.unix_events._UnixSelectorEventLoop.create_server')
    def test_001_build_server(self, call_create_server, call_make_handler):
        self._loop.run_until_complete(self._api.build(self._host,
                                                      self._port))
        eq_(call_make_handler.call_count, 1)
        eq_(self._api._handler, True)
        eq_(call_create_server.call_count, 1)
        call_create_server.assert_called_with(self._api._handler,
                                              host=self._host,
                                              port=self._port)

    def test_002_destroy_server(self):
        with patch.object(self._api, "_handler") as i_handler:
            i_handler.finish_connection.return_value = []
            with patch.object(self._api, "_server") as i_server:
                i_server.wait_closed.return_value = []
                with patch.object(self._api._server, "close") as call_close:
                    self._loop.run_until_complete(self._api.destroy())
                    eq_(call_close.call_count, 1)
                    eq_(i_server.wait_closed.call_count, 1)

    def test_003_instantiated_router(self):
        assert_is(self._api.router, self._api._app.router)


class TestJsonMiddleware(AsyncTestCase):

    def setUp(self):
        super().setUp()
        self._request = Mock()
        self._request.POST_METHODS = ['POST', 'PUT', 'PATCH']
        self._app = Mock()

    def test_001_request_valid_header_content_post_method(self):
        self._request.headers = {'CONTENT-TYPE': 'application/json'}
        ret_value = {'test_value': 'kikoo_test'}
        self._request.json.return_value = ret_value
        self._request.method = 'POST'

        @fake_future
        def _next_handler(r):
            return ret_value

        mdw = self._loop.run_until_complete(mw_json(self._app, _next_handler))
        assert_is_not_none(mdw)
        response = self._loop.run_until_complete(mdw(self._request))
        eq_(response, ret_value)

    def test_002_request_handling_non_post_method(self):
        self._request.headers = {}
        ret_value = True
        self._request.method = 'GET'

        @fake_future
        def _next_handler(r):
            return ret_value

        mdw = self._loop.run_until_complete(mw_json(self._app, _next_handler))
        assert_is_not_none(mdw)
        response = self._loop.run_until_complete(mdw(self._request))
        eq_(response, ret_value)

    def test_003_request_invalid_or_missing_header(self):
        headers = [{}, {'CONTENT-TYPE': 'application/octet-stream'}]
        self._request.method = 'POST'

        for h in headers:
            self._request.headers = h
            mdw = self._loop.run_until_complete(mw_json(self._app, Mock()))
            assert_is_not_none(mdw)
            assert_raises(
                errors.HttpBadRequest,
                self._loop.run_until_complete,
                mdw(self._request))


class TestCapabilityMiddleware(AsyncTestCase):

    def setUp(self):
        super().setUp()
        self._request = Mock()
        self._request.POST_METHODS = ['POST', 'PUT', 'PATCH']
        self._app = Mock()

    def test_001a_extract_data_from_payload_post_method(self):
        self._request.method = 'POST'
        data = bytes(dumps({'response': 'ok'}), 'utf-8')

        @fake_future
        def json():
            return {'capability': 'string_manip'}

        self._request.json = json

        @fake_future
        def _capa_handler(d):
            capa_resp = Mock(api_payload=data, status=200)
            return capa_resp

        mdw = self._loop.run_until_complete(
            mw_capability(self._app, _capa_handler))
        assert_is_not_none(mdw)
        response = self._loop.run_until_complete(mdw(self._request))
        assert_true(isinstance(response, web.Response))
        eq_(loads(response.body.decode('utf-8'))["response"], 'ok')
        eq_(response.status, 200)

    def test_001b_extract_data_from_non_post_method(self):
        self._request.method = 'GET'
        self._request.GET = {'id': 2}
        data = bytes(dumps({'response': 2}), 'utf-8')

        @fake_future
        def _capa_handler(d):
            capa_resp = Mock(
                api_payload=data,
                status=200)
            return capa_resp

        mdw = self._loop.run_until_complete(
            mw_capability(self._app, _capa_handler))
        assert_is_not_none(mdw)
        response = self._loop.run_until_complete(mdw(self._request))
        assert_true(isinstance(response, web.Response))
        eq_(loads(response.body.decode('utf-8'))["response"], 2)
        eq_(response.status, 200)

    def test_002_error_handling_post_method_no_json(self):
        self._request.method = 'POST'
        data = 'data_no_json'

        @fake_future
        def json():
            return loads(data)

        self._request.json = json

        @fake_future
        def _capa_handler():
            pass

        mdw = self._loop.run_until_complete(
            mw_capability(self._app, _capa_handler))
        assert_is_not_none(mdw)
        assert_raises(
            errors.BadHttpMessage,
            self._loop.run_until_complete,
            mdw(self._request))
