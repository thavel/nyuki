import json
import os
from nose.tools import eq_, assert_true, assert_false, assert_not_equal
from unittest import TestCase

from nyuki import Nyuki


class TestNyuki(TestCase):

    def setUp(self):
        kwargs = {
            'jid': 'test@localhost',
            'password': 'test',
            'server': '127.0.0.1:5555',
            'api': 'localhost:8082',
            'logging': 'DEBUG'
        }
        self.nyuki = Nyuki(**kwargs)
        self.nyuki.config_filename = 'unit_test_conf.json'

    def tearDown(self):
        if os.path.isfile(self.nyuki.config_filename):
            os.remove(self.nyuki.config_filename)

    def test_001_init(self):
        bus_loop = self.nyuki._bus._loop.loop
        exposer_loop = self.nyuki._exposer._loop
        eq_(bus_loop, exposer_loop)

    def test_002_load_config(self):
        config = dict(self.nyuki.config)
        config['new_config'] = True
        with open(self.nyuki.config_filename, 'w') as jsonfile:
            json.dump(config, jsonfile)
        self.nyuki.load_config(config=self.nyuki.config_filename)
        assert_true(self.nyuki.config['new_config'])

    def test_003_update_config(self):
        assert_not_equal(
            self.nyuki.config['bus']['password'], 'new_password')
        self.nyuki.update_config('new_password', 'bus.password')
        eq_(self.nyuki.config['bus']['password'], 'new_password')

    def test_004_save_config(self):
        assert_false(os.path.isfile(self.nyuki.config_filename))
        self.nyuki.save_config()
        assert_true(os.path.isfile(self.nyuki.config_filename))
        with open(self.nyuki.config_filename) as file:
            conf = json.loads(file.read())
        eq_(self.nyuki.config, conf)

    def test_005_get_rest_configuration(self):
        response = self.nyuki.Configuration.get(self.nyuki, None)
        eq_(json.loads(bytes.decode(response.api_payload)), self.nyuki._config)

    def test_006_put_rest_configuration(self):
        self.nyuki.Configuration.put(self.nyuki, {
            'bus': {'jid': 'updated@localhost'},
            'new': True
        })
        eq_(self.nyuki._config['new'], True)
        eq_(self.nyuki._config['bus']['jid'], 'updated@localhost')
