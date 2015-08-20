import json
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
            'request decoder',
            StanzaPath('iq@type=set/request'),
            self._decode_request))

        register_stanza_plugin(Iq, Request)
        register_stanza_plugin(Iq, Response)

    def _decode_request(self, iq):
        self.xmpp.event('nyuki_request', iq)

    def plugin_end(self):
        self.xmpp.remove_handler('request decoder')
