from unittest import TestCase
from mock import Mock, patch

from nyuki.commands import get_command_kwargs


class TestCommand(TestCase):

    @patch('nyuki.commands._build_args')
    def test_001_get_command_kwargs(self, _build_args):
        # Arguments parsed
        args = Mock()
        args.config = 'config.json'
        args.jid = 'test@localhost'
        args.password = 'test'
        args.server = '127.0.0.1:5555'
        args.api = 'localhost:8082'
        args.logging = 'DEBUG'
        _build_args.return_value = args

        # Result
        kwargs = get_command_kwargs()
        expected = {
            'config': 'config.json',
            'jid': 'test@localhost',
            'password': 'test',
            'server': '127.0.0.1:5555',
            'api': 'localhost:8082',
            'logging': 'DEBUG'
        }
        self.assertEqual(kwargs, expected)
