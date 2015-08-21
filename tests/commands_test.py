from unittest import TestCase
from mock import Mock, patch

from nyuki.commands import (_update_config, _merge_config, parse_init,
                            exhaustive_config)


class TestUpdateConfig(TestCase):

    def test_001_call(self):
        source = {'a': 1, 'b': {'c': 2}}
        # Update
        _update_config(source, '1', 'a')
        self.assertEqual(source['a'], '1')
        # Nested update
        _update_config(source, 3, 'b.c')
        self.assertEqual(source['b']['c'], 3)
        # Create
        _update_config(source, 4, 'b.d')
        self.assertEqual(source['b']['d'], 4)


class TestMergeConfig(TestCase):

    def test_001_call(self):
        dict1 = {'a': 1, 'b': {'c': 2}}
        dict2 = {'b': {'d': 3}}
        result = _merge_config(dict1, dict2)
        self.assertEqual(result, {'a': 1, 'b': {'c': 2, 'd': 3}})


class TestParseInit(TestCase):

    @patch('nyuki.commands._read_file')
    @patch('nyuki.commands._build_args')
    def test_001_call(self, _build_args, _read_file):
        # Arguments parsed
        args = Mock()
        args.cfg = 'config.json'
        args.jid = 'test@localhost'
        args.pwd = 'test'
        args.srv = '127.0.0.1:5555'
        args.api = 'localhost:8082'
        args.debug = True
        _build_args.return_value = args
        # Config file
        _read_file.return_value = {
            'bus': {
                'jid': 'iamrobert',
                'password': 'mysuperstrongpassword',
            }
        }
        # Result
        configs = parse_init()
        self.assertEqual(configs, {
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
        })


class TestExhaustiveConfig(TestCase):

    def test_001_call(self):
        parsed_configs = {
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
        self.assertIsInstance(exhaustive_config(parsed_configs), dict)
        wrong_config = {
            'bus': {
                'jid': 'test@localhost'
            }
        }
        with self.assertRaises(SystemExit) as call:
            exhaustive_config(wrong_config)
        self.assertEqual(call.exception.code, 1)
