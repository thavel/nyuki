from nose.tools import eq_
from unittest import TestCase
from unittest.mock import Mock, patch

from nyuki.api import Response
from nyuki.capabilities import resource, Capability, Exposer


class TestResourceDecorator(TestCase):

    def test_001_call(self):
        @resource(endpoint='/test', version='v1')
        class Test:
            pass
        self.assertEqual(Test.endpoint, '/test')
        self.assertEqual(Test.version, 'v1')


class TestCapability(TestCase):

    def setUp(self):
        handler = (lambda x: x)
        self.capability = Capability(
            name='test',
            method='GET',
            endpoint='/test',
            version=None,
            handler=handler,
            wrapper=staticmethod(handler),
        )

    def test_001_hash(self):
        self.assertEqual(self.capability.__hash__(), hash(self.capability.name))


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


class TestExposer(TestCase):

    def setUp(self):
        loop = Mock()
        self.handler = (lambda x: x)
        self.exposer = Exposer(loop)
        self.capability = Capability(
            name='test',
            method='GET',
            endpoint='/test',
            version='v1',
            handler=self.handler,
            wrapper=self.handler,
        )

    @patch('aiohttp.web_urldispatcher.UrlDispatcher.add_route')
    def test_001_register(self, add_route):
        self.exposer.register(self.capability)
        self.assertRaises(ValueError, self.exposer.register, self.capability)
        add_route.assert_called_with('GET', '/v1/test', self.handler)

    def test_002_find(self):
        self.assertIsNone(self.exposer._find('hello'))
        self.exposer.register(self.capability)
        self.assertEqual(self.exposer._find('test'), self.capability)
