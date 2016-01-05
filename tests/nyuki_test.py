import json
from jsonschema import ValidationError
import os
from nose.tools import (
    eq_, assert_true, assert_false, assert_not_equal, assert_raises
)
from unittest import TestCase
from unittest.mock import patch

from nyuki import Nyuki
from tests import AsyncMock, make_future


class TestNyuki(TestCase):

    def setUp(self):
        kwargs = {
            'bus': {
                'jid': 'test@localhost',
                'password': 'test',
                'host': '127.0.0.1',
                'port': 5555
            },
            'api': {
                'host': 'localhost',
                'port': 8082
            },
            'logging': 'DEBUG'
        }
        self.nyuki = Nyuki(**kwargs)
        self.loop = self.nyuki.loop
        self.nyuki.config_filename = 'unit_test_conf.json'

    def tearDown(self):
        if os.path.isfile(self.nyuki.config_filename):
            os.remove(self.nyuki.config_filename)

    def test_001_update_config(self):
        assert_not_equal(
            self.nyuki.config['bus']['password'], 'new_password')
        self.nyuki.update_config({
            'bus': {
                'password': 'new_password'
            }
        })
        eq_(self.nyuki.config['bus']['password'], 'new_password')

    def test_003_save_config(self):
        assert_false(os.path.isfile(self.nyuki.config_filename))
        self.nyuki.save_config()
        assert_true(os.path.isfile(self.nyuki.config_filename))
        with open(self.nyuki.config_filename) as file:
            conf = json.loads(file.read())
        eq_(self.nyuki.config, conf)

    def test_002_get_rest_configuration(self):
        response = self.nyuki.Configuration.get(self.nyuki, None)
        eq_(json.loads(bytes.decode(response.api_payload)), self.nyuki._config)

    @patch('nyuki.bus.Bus.stop', return_value=AsyncMock())
    def test_003_patch_rest_configuration(self, bus_stop_mock):
        bus_stop_mock.return_value = make_future()
        self.loop.run_until_complete(
            self.nyuki.Configuration.patch(self.nyuki, {
                'bus': {'jid': 'updated@localhost'},
                'new': True
            })
        )
        eq_(self.nyuki._config['new'], True)
        eq_(self.nyuki._config['bus']['jid'], 'updated@localhost')
        bus_stop_mock.assert_called_once_with()

    def test_004a_custom_schema_fail(self):
        with assert_raises(ValidationError):
            self.nyuki.register_schema({
                'type': 'object',
                'required': ['port'],
                'properties': {
                    'port': {
                        'type': 'integer',
                    }
                }
            })

    def test_004b_custom_schema_ok(self):
        self.nyuki._config['port'] = 4000
        self.nyuki.register_schema({
            'type': 'object',
            'required': ['port'],
            'properties': {
                'port': {'type': 'integer'}
            }
        })
        # Base + API + Bus + custom
        eq_(len(self.nyuki._schemas), 4)

    def test_005_stop(self):
        with patch.object(self.nyuki.services, 'stop', new=AsyncMock()) as mock:
            self.loop.run_until_complete(self.nyuki.stop())
            mock.assert_called_once_with()
        assert_true(self.nyuki.is_stopping)
