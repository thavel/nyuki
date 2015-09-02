from jsonschema import ValidationError
from nose.tools import assert_raises
from unittest import TestCase
from unittest.mock import patch, Mock

from nyuki.config import (
    update_config, get_full_config, merge_configs
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


class TestMergeConfigs(TestCase):

    def test_001_call_error(self):
        dict1 = {'a': 1, 'b': {'c': 2}}
        dict2 = {'b': {'d': 3}}
        dict3 = {'a': {'e': 2}}
        with assert_raises(ValidationError):
            result = merge_configs(dict1, dict2, dict3)


class TestGetFullConfig(TestCase):

    @patch('nyuki.config.read_conf_json')
    def test_001_file_conf(self, read_conf_json):
        self.maxDiff = None
        fileconf = {
            'bus': {
                'jid': 'test@localhost',
                'password': 'test',
                'host': '127.0.0.1',
                'port': 5555
            }
        }
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
        self.maxDiff = None
        fileconf = {
            'bus': {
                'jid': 'test@localhost',
                'password': 'test',
                'host': '127.0.0.1',
                'port': 5555
            }
        }
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
            api={'host': 'localhost', 'port': 5152},
            log={'root': {'level': 'DEBUG'}}
        ), expected)
