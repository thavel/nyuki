from unittest import TestCase
from mock import patch

from nyuki.config import (
    update_config, _merge_config, get_full_config
)
from nyuki.logs import DEFAULT_LOGGING


class TestUpdateConfig(TestCase):

    def test_001_call(self):
        source = {'a': 1, 'b': {'c': 2}}
        # Update
        update_config(source, '1', 'a')
        self.assertEqual(source['a'], '1')
        # Nested update
        update_config(source, 3, 'b.c')
        self.assertEqual(source['b']['c'], 3)
        # Create
        update_config(source, 4, 'b.d')
        self.assertEqual(source['b']['d'], 4)


class TestMergeConfig(TestCase):

    def test_001_call(self):
        dict1 = {'a': 1, 'b': {'c': 2}}
        dict2 = {'b': {'d': 3}}
        result = _merge_config(dict1, dict2)
        self.assertEqual(result, {'a': 1, 'b': {'c': 2, 'd': 3}})


class TestGetFullConfig(TestCase):

    @patch('nyuki.config.read_conf_json')
    def test_001_file_conf(self, read_conf_json):
        self.maxDiff = None
        fileconf = {'bus': {
            'jid': 'test@localhost',
            'password': 'test',
            'host': '127.0.0.1',
            'port': 5555
        }}
        read_conf_json.return_value = fileconf
        expected = {
            'bus': {
                'jid': 'test@localhost',
                'password': 'test',
                'host': '127.0.0.1',
                'port': 5555
            },
            'api': dict(),
            'log': DEFAULT_LOGGING
        }

        self.assertEqual(get_full_config(config='conf.json'), expected)

    def test_003_file_conf_err(self):
        with self.assertRaises(Exception):
            get_full_config(config='inexisting_conf.json')

    @patch('nyuki.config.read_conf_json')
    def test_004_full_conf(self, read_conf_json):
        fileconf = {'bus': {
            'jid': 'test@localhost',
            'password': 'test',
            'host': '127.0.0.1',
            'port': 5555
        }}
        read_conf_json.return_value = fileconf

        debug_logging = DEFAULT_LOGGING
        debug_logging['root']['level'] = 'DEBUG'
        expected = {
            'bus': {
                'jid': 'test@localhost',
                'password': 'test',
                'host': '127.0.0.1',
                'port': 5555
            },
            'api': {'port': 5152, 'host': 'localhost'},
            'log': debug_logging
        }
        self.assertEqual(get_full_config(
            config='conf.json',
            api='localhost:5152',
            logging='DEBUG'
        ), expected)
