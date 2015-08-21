import logging
from slixmpp.plugins import BasePlugin
from slixmpp.stanza import Iq
from slixmpp.xmlstream import register_stanza_plugin
from slixmpp.xmlstream.handler import Callback
from slixmpp.xmlstream.matcher import StanzaPath

from . import stanza
from .stanza import Request, Response


log = logging.getLogger(__name__)


class XEP_Nyuki(BasePlugin):

    name = 'xep_nyuki'
    description = 'XEP-Nyuki: Capability/Body requests'
    dependencies = set()
    stanza = stanza

    def plugin_init(self):
        self.xmpp.register_handler(Callback(
            'nyuki request',
            StanzaPath('iq@type=set/request'),
            self._nyuki_request))

        self.xmpp.register_handler(Callback(
            'nyuki response',
            StanzaPath('iq@type=set/response'),
            self._nyuki_request))

        register_stanza_plugin(Iq, Request)
        register_stanza_plugin(Iq, Response)

    def _nyuki_request(self, iq):
        self.xmpp.event('nyuki_request', iq)

    def _nyuki_response(self, iq):
        self.xmpp.event('nyuki_response', iq)

    def plugin_end(self):
        self.xmpp.remove_handler('request decoder')
