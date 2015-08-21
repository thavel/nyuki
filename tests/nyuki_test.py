from unittest import TestCase

from nyuki import Nyuki


class TestNyuki(TestCase):

    def setUp(self):
        self.config = {
            'bus': {
                'jid': 'test@localhost',
                'password': 'test',
                'host': '127.0.0.1',
                'port': 5555
            },
            'api': {
                'port': 8082,
                'host': 'localhost'
            },
            'log': {
                'root': {
                    'level': 'DEBUG'}
            }
        }
        self.nyuki = Nyuki(conf=self.config)

    def test_001_init(self):
        bus_loop = self.nyuki._bus._loop.loop
        exposer_loop = self.nyuki._exposer._loop
        self.assertEqual(bus_loop, exposer_loop)
