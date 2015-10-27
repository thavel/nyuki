import asyncio
import json
from jsonschema import ValidationError
import os
from nose.tools import (
    eq_, assert_true, assert_false, assert_not_equal, assert_raises
)
from unittest import TestCase
from unittest.mock import patch

from nyuki import Nyuki


class TestNyuki(TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
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
        self.nyuki.config_filename = 'unit_test_conf.json'

    def tearDown(self):
        if os.path.isfile(self.nyuki.config_filename):
            os.remove(self.nyuki.config_filename)

    def test_001_init(self):
        bus_loop = self.nyuki._bus._loop
        exposer_loop = self.nyuki._exposer._loop
        eq_(bus_loop, exposer_loop)

    def test_002_update_config(self):
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

    def test_004_get_rest_configuration(self):
        response = self.nyuki.Configuration.get(self.nyuki, None)
        eq_(json.loads(bytes.decode(response.api_payload)), self.nyuki._config)

    def test_005_patch_rest_configuration(self):
        self.nyuki.Configuration.patch(self.nyuki, {
            'bus': {'jid': 'updated@localhost'},
            'new': True
        })
        eq_(self.nyuki._config['new'], True)
        eq_(self.nyuki._config['bus']['jid'], 'updated@localhost')

    def test_006a_custom_schema_fail(self):
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

    def test_006b_custom_schema_ok(self):
        self.nyuki._config['port'] = 4000
        self.nyuki.register_schema({
            'type': 'object',
            'required': ['port'],
            'properties': {
                'port': {
                    'type': 'integer',
                }
            }
        })
        eq_(len(self.nyuki._schemas), 2)

    @patch('slixmpp.xmlstream.XMLStream.disconnect')
    def test_007_stop(self, disconnect_mock):
        # TODO: This test throws stderr errors (not bad, but ugly)

        def disconnected(wait):
            self.nyuki._bus.client.disconnected.set_result(True)
        disconnect_mock.side_effect = disconnected

        with patch.object(self.nyuki, 'teardown') as mock:
            self.nyuki.stop = asyncio.coroutine(self.nyuki.stop)
            self.loop.run_until_complete(self.nyuki.stop())
            mock.assert_called_once_with()
            assert_true(self.nyuki.is_stopping)

    @patch('slixmpp.xmlstream.XMLStream.connect')
    def test_007_stop_unwanted(self, connect):

        self.nyuki._bus.client.disconnected.set_result(True)
        self.loop.run_until_complete(asyncio.sleep(0))
        eq_(connect.call_count, 1)
