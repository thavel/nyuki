from mock import patch

from unittest import TestCase
from sleekxmpp import ClientXMPP, Message, JID

from nyuki.messaging.message_factory import MessageFactory, Codes


class TestMessageFactory(TestCase):

    def setUp(self):
        self.factory = MessageFactory(ClientXMPP('test', 'test'))

    def tearDown(self):
        self.factory = None

    def test_001_generate_uid(self):
        uid1 = self.factory._generate_uid()
        uid2 = self.factory._generate_uid()
        self.assertTrue(isinstance(uid1, str))
        self.assertNotEqual(uid1, uid2)

    def test_002a_build_message_for_unicast(self):
        with patch.object(self.factory.xmpp_client, 'make_message') as mock:
            self.factory._build_message_for_unicast('msg', 'to', is_json=False)
            mock.assert_called_once_with(mbody='msg', msubject='PROCESS', mto='to', mtype='normal')

        msg = self.factory._build_message_for_unicast('msg', 'to', is_json=False)
        self.assertTrue(isinstance(msg, Message))

    def test_002b_build_message_for_unicasti_json(self):
        expected = {
            'body': '{"msg": "toto"}', 'from': JID(), 'id': '',
            'lang': 'en', 'mucnick': '', 'mucroom': '',
            'parent_thread': '', 'subject': 'PROCESS',
            'thread': '', 'to': JID('to'), 'type': 'normal'
        }
        msg = self.factory._build_message_for_unicast({'msg': 'toto'}, 'to', is_json=True)
        self.assertTrue(isinstance(msg, Message))
        self.assertEqual(dict(msg), expected)

    def test_003_build_request_unicast_message(self):
        expected = {
            'body': 'toto', 'from': None, 'id': '666',
            'lang': 'en', 'mucnick': '', 'mucroom': '',
            'parent_thread': '', 'subject': 'process',
            'thread': '', 'to': 'tata', 'type': 'normal'
        }
        self.assertNotIn('666', self.factory.requests)

        msg = self.factory.build_request_unicast_message(
            msg='toto', to='tata', msg_id='666'
        )
        self.assertTrue(isinstance(msg, Message))
        self.assertEqual(dict(msg), expected)
        self.assertEqual(self.factory.requests[msg['id']], {})

    def test_004_build_response_unicast_message_ok(self):
        msg = self.factory.build_response_unicast_message(
                msg='toto',
                to='tata',
                subject=Codes('200_OK'),
                msg_id='666'
            )
        self.assertTrue(isinstance(msg, Message))
        self.assertEqual(dict(msg)['subject'], '200_OK')

    def test_004_build_response_unicast_message_nocode(self):
        with self.assertRaises(ValueError):
            self.factory.build_response_unicast_message(
                msg='toto',
                to='tata',
                subject=Codes('000'),
                msg_id='666'
            )
        with self.assertRaises(ValueError):
            self.factory.build_response_unicast_message(
                msg='toto',
                to='tata',
                subject='unknown',
                msg_id='666'
            )
