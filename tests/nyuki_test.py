from unittest import TestCase
from mock import patch

import threading

from nyuki.nyuki import Nyuki
from nyuki.messaging.nbus import Nbus


class TestNyuki(TestCase):

    def setUp(self):
        self.nyuki = Nyuki()

    def tearDown(self):
        self.nyuki = None

    def test_001_run(self):
        with patch.object(self.nyuki.bus, 'connect') as mock:
            self.nyuki.run()
            mock.assert_called_once_with()

    @patch.object(Nbus, 'disconnect')
    def test_002a__kill_valid(self, mock):
        '''
        Disconnect from the bus
        clean the ioloop
        '''
        self.nyuki._kill(9, 0)
        mock.assert_called_once_with()

    @patch.object(Nbus, 'disconnect')
    def test_002b__kill_valid(self, mock):
        '''
        Disconnect from the bus
        clean the ioloop
        '''
        self.nyuki._stopping.set()
        self.nyuki._kill(9, 0)
        self.assertFalse(mock.called)

    @patch.object(Nbus, 'disconnect')
    def test_003_stop(self, mock):
        self.nyuki.toto = 35
        self.nyuki._thread = threading.Thread()
        self.nyuki._thread.start()
        with patch.object(self.nyuki._thread, 'join') as thread_mock:
            self.nyuki.stop()
            self.assertTrue(self.nyuki._stopping.is_set())
            mock.assert_called_once_with()
            thread_mock.asssert_called_once_with()
