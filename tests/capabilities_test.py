from unittest import TestCase
from unittest.mock import Mock, patch

from nyuki.capabilities import (resource, Capability, Response, Exposer)


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

    def setUp(self):
        self.response = Response(body={'message': 'hello'}, status=200)

    def test_001a_valid(self):
        self.assertIsNone(self.response._is_valid())

    def test_001b_valid_error(self):
        self.response.body = 'hello'
        self.assertRaises(ValueError, self.response._is_valid)

    def test_001c_valid_error(self):
        self.response.body = '404'
        self.assertRaises(ValueError, self.response._is_valid)

    def test_002_payload(self):
        self.assertIsInstance(self.response.api_payload, bytes)


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
