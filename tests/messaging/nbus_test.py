from mock import patch
from unittest import TestCase

from sleekxmpp import Iq

from nyuki.messaging.nbus import Nbus, XMPPClient, IqTimeout


class TestNbus(TestCase):

    def setUp(self):
        self.nbus = Nbus('test@localhost', 'test')

    def tearDown(self):
        if self.nbus.is_connected:
            self.nbus.disconnect()
        self.nbus = None

    def test_001__init(self):
        self.assertEqual(self.nbus._status, 'disconnected')

    def test_002_init_xmpp(self):
        xmpp = self.nbus._init_xmpp('test_xmpp@localhost', 'test')
        self.assertTrue(isinstance(xmpp, XMPPClient))

    @patch.object(XMPPClient, 'process')
    def test_003_connect(self, process_mock):
        '''
        To Fix, lead to an endless loop !
        '''
        self.nbus._init_xmpp('test_xmpp@localhost', 'test')
        with patch.object(self.nbus.xmpp, 'connect', return_value=True) as mock:
            self.nbus.connect()
            mock.assert_called_once_with(reattempt=False)
            process_mock.assert_called_once_with()

    @patch.object(Nbus, 'disconnect')
    def test_004_on_register(self, mock):
        with patch.object(Iq, 'send', side_effect=IqTimeout(iq=0)):
            self.nbus._status = 'connected'
            self.nbus._on_register(self)
            mock.assert_called_once_with()
