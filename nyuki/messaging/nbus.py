import logging
from slixmpp import ClientXMPP
from slixmpp.exceptions import IqError, IqTimeout

from nyuki.messaging.event import (
    EventManager, Disconnected, MessageReceived, SessionStart
)
from nyuki.messaging.message_factory import MessageFactory


log = logging.getLogger(__name__)


class XMPPClient(ClientXMPP):

    """
    A pre-configured and customized XMPP client based on `sleekxmpp.ClientXMPP`.
    This class is a simple wrapper that intends to make communication on the
    nyuki bus easy.
    """

    def __init__(self, jid, password, **kwargs):
        """
        Set the default configuration of the XMPP client and add default
        host/port settings.
        """
        try:
            host = kwargs.pop('host')
        except KeyError:
            host = jid.split('@')[1]
        try:
            port = int(kwargs.pop('port'))
        except KeyError:
            port = 5222
        self._address = (host, port)
        super().__init__(jid, password, **kwargs)
        # Need MUC and Service Administration XEPs
        self.register_plugin('xep_0045')
        self.register_plugin('xep_0133')
        self.register_plugin('xep_0077')  # In-band registration
        # Disable IPv6 support until we really need it!
        self.use_ipv6 = False

    def connect(self, address=tuple(), **kwargs):
        """
        Disable SRV lookups by always passing to `connect()` an address.
        """
        addr = address if address else self._address
        return super().connect(address=addr, **kwargs)


class Nbus(object):

    """
    This class intends to provide a clean API to easily handle messages on the
    bus (incoming and outgoing).
    """

    def __init__(self, jid, password, event_stack=None, **kwargs):
        """
        Initialize the bus with `host` and `port` as optional keyword arguments
        """
        if event_stack:
            self._event_stack = event_stack
            event_stack.register(self)
        else:
            self._event_stack = EventManager(self)
        self.xmpp = self._init_xmpp(jid, password, **kwargs)
        self.factory = MessageFactory(self.xmpp)

    def fire(self, event):
        raise NotImplementedError

    def _init_xmpp(self, jid, password, **kwargs):
        """
        Create and configure the XMPP client.
        """
        xmpp = XMPPClient(jid, password, **kwargs)
        xmpp.add_event_handler('session_start', self._on_start)
        xmpp.add_event_handler('message', self._on_message)
        xmpp.add_event_handler('disconnected', self._on_disconnect)
        xmpp.add_event_handler("register", self._on_register)
        return xmpp

    def is_connected(self):
        return self.xmpp.is_connected()

    def connect(self):
        self.xmpp.connect()
        self.xmpp.process(forever=False)

    def disconnect(self, **kwargs):
        self.xmpp.disconnect(**kwargs)

    def send_unicast(self, message):
        """
        The message argument should be an instance of
        sleekxmpp.stanza.Message
        """
        message.send()

    def send_multicast(self, group, id):
        """
        TBD!
        """

    def _on_start(self, _):
        self.xmpp.send_presence()
        self.xmpp.get_roster()
        self.fire(SessionStart())

    def _on_message(self, msg):
        self.fire(MessageReceived(message=msg))

    def _on_disconnect(self, _):
        self.fire(Disconnected())

    def _on_register(self, _):
        resp = self.xmpp.Iq()
        resp['type'] = 'set'
        resp['register']['username'] = self.xmpp.boundjid.user
        resp['register']['password'] = self.xmpp.password

        try:
            # TODO: catch these errors (inside async call)
            resp.send()
        except IqError as iqex:
            err = iqex.iq['error']['text']
            log.warning(
                "Could not register account: {msg}".format(msg=err)
            )
        except IqTimeout:
            log.error("No response from the server")
            self.disconnect()
        else:
            log.info(
                "Account created for {jid}".format(jid=self.xmpp.boundjid)
            )
