from aiohttp.web_urldispatcher import UrlDispatcher
from nose.tools import eq_
from unittest import TestCase
from unittest.mock import Mock, patch

from nyuki.api.api import Api, ResourceClass, Response, resource


class TestResourceDecorator(TestCase):

    def test_001_call(self):
        @resource('/test', versions=['v1'])
        class Test:
            pass
        self.assertEqual(Test.RESOURCE_CLASS.path, '/test')
        self.assertEqual(Test.RESOURCE_CLASS.versions, ['v1'])


class TestResponse(TestCase):

    def test_001_dict_body(self):
        response = Response({'test': 'test'})
        eq_(response.body, b'{"test": "test"}')
        eq_(response.content_type, 'application/json')

    def test_002_other_body(self):
        response = Response(123)
        eq_(response.body, b'123')
        eq_(response.content_type, 'text/plain')

        response = Response('hello')
        eq_(response.body, b'hello')
        eq_(response.content_type, 'text/plain')


class TestResourceClass(TestCase):

    class TestResource:

        async def get(self, request):
            pass

        async def delete(self, request):
            pass

    def setUp(self):
        loop = Mock()
        self.api = Api(loop)
        self.resource_cls = ResourceClass(
            self.TestResource, '/test', ['v1', 'v2'], 'application/json'
        )

    @patch('aiohttp.web_urldispatcher.Resource.add_route')
    def test_001_register(self, add_route):
        router = UrlDispatcher()
        self.resource_cls.register(Mock(), router)
        # GET /v1/test
        # DELETE /v1/test
        # GET /v2/test
        # DELETE /v2/test
        self.assertEqual(add_route.call_count, 4)
