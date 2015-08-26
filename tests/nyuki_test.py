import os
import json
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
        self.assertEqual(bus_loop, exposer_loop)

    def test_002_load_config(self):
        config = dict(self.nyuki.config)
        config['new_config'] = True
        with open(self.nyuki.config_filename, 'w') as jsonfile:
            json.dump(config, jsonfile)
        self.nyuki.load_config(config=self.nyuki.config_filename)
        self.assertTrue(self.nyuki.config['new_config'])

    def test_003_update_config(self):
        self.assertNotEqual(self.nyuki.config['bus']['password'],
                            'new_password')
        self.nyuki.update_config('new_password', 'bus.password')
        self.assertEqual(self.nyuki.config['bus']['password'],
                         'new_password')

    def test_004_save_config(self):
        self.assertFalse(os.path.isfile(self.nyuki.config_filename))
        self.nyuki.save_config()
        self.assertTrue(os.path.isfile(self.nyuki.config_filename))
        with open(self.nyuki.config_filename) as file:
            conf = json.loads(file.read())
        self.assertEqual(self.nyuki.config, conf)
