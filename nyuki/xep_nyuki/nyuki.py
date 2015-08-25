import logging
from slixmpp.plugins import BasePlugin
from slixmpp.stanza import Message
from slixmpp.xmlstream import register_stanza_plugin
from slixmpp.xmlstream.handler import Callback
from slixmpp.xmlstream.matcher import StanzaPath, MatchXPath

from . import stanza
from .stanza import NyukiEvent, NyukiRequest, NyukiResponse


log = logging.getLogger(__name__)


class XEP_Nyuki(BasePlugin):

    name = 'xep_nyuki'
    description = 'XEP-Nyuki: Capability/Body requests'
    dependencies = set()
    stanza = stanza

    def plugin_init(self):
        self.xmpp.register_handler(Callback(
            'nyuki event',
            StanzaPath('message/{nyuki}event'),
            self._nyuki_event))

        self.xmpp.register_handler(Callback(
            'nyuki request',
            StanzaPath('message/{nyuki}request'),
            self._nyuki_request))

        register_stanza_plugin(Message, NyukiEvent)
        register_stanza_plugin(Message, NyukiRequest)
        register_stanza_plugin(Message, NyukiResponse)

    def _nyuki_event(self, event):
        self.xmpp.event('nyuki_event', event)

    def _nyuki_request(self, request):
        self.xmpp.event('nyuki_request', request)

    def plugin_end(self):
        self.xmpp.remove_handler('request decoder')
