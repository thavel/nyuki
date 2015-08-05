import logging
from queue import Queue
from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout

from nyuki.messaging.event import on_event, Event, EventManager, list_events


class Connected(Event):
    pass

class Connecting(Event):
    pass

class ConnectionError(Event):
    pass

class Disconnected(Event):
    pass

class MessageReceived(Event):
    def __init__(self, message=None):
        self.message = message

class SessionStart(Event):
    pass

class AnnounceSuccess(Event):
    def __init__(self, subject=None):
        self.subject = subject

class AnnounceError(Event):
    def __init__(self, subject=None):
        self.subject = subject


EVENTS = list_events(__name__)
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
        super(XMPPClient, self).__init__(jid, password, **kwargs)
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
        return super(XMPPClient, self).connect(address=addr, **kwargs)


class Nbus(object):
    """
    This class intends to provide a clean API to easily handle messages on the
    bus (incoming and outgoing).
    """
    received_queue = Queue()
    STATUSES = {
        'connected',
        'diconnected',
        'connecting'
    }

    def __init__(self, jid, password, event_stack=None, **kwargs):
        """
        Initialize the bus with `host` and `port` as optional keyword arguments
        """
        super(Nbus, self).__init__()
        self.xmpp = self._init_xmpp(jid, password, **kwargs)
        self._status = 'disconnected'
        self.log = logging.getLogger(__name__)
        if event_stack:
            self._event_stack = event_stack
            event_stack.register(self)
        else:
            self._event_stack = EventManager(self)

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

    def connect(self, reattempt=False, **kwargs):
        self.fire(Connecting())
        if self.xmpp.connect(reattempt=False, **kwargs):
            self.xmpp.process()
            self.fire(Connected())
        else:
            self.fire(ConnectionError())

    def disconnect(self, **kwargs):
        self.xmpp.disconnect(**kwargs)

    @property
    def status(self):
        return self._status

    @property
    def is_connected(self):
        return self._status == 'connected'

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

    def send_broadcast(self, subject, announcement, success_callback=None,
                       error_callback=None):
        """
        Use XEP-133 to broadcast announce
        """

        def annouce_error(iq, session):
            error_condition = iq['error']['condition']
            error_text = iq['error']['text']
            self.log.error("Announce error: " +
                              " condition=%s; text=%s" % (error_condition,
                                                          error_text))
            self.fire(AnnounceError(subject=subject))
            # self.xmpp['xep_0050'].complete_command(session)

        def announce_success(iq, session):
            self.fire(AnnounceSuccess(subject=subject))
            self.log.debug("Announce: subject=%s; announcement=%s is sent" %
                              (subject, announcement))

        def process_announce(iq, session):
            form = iq['command']['form']
            answers = {}

            for var, field in form['fields'].items():
                if var == 'FORM_TYPE':
                    answers[var] = field['value']
                    break

            answers["subject"] = subject
            answers['announcement'] = announcement
            form["type"] = "submit"
            form["values"] = answers
            session["payload"] = form
            session["next"] = success_callback or announce_success
            session["error"] = error_callback or annouce_error

            self.xmpp['xep_0050'].complete_command(session)

        session = {"next": process_announce,
                   "error": annouce_error}
        self.xmpp['xep_0133'].announce(session=session)

    def _on_start(self, event):
        self.xmpp.send_presence()
        self.xmpp.get_roster()
        self.fire(SessionStart())

    def _on_message(self, msg):
        self.fire(MessageReceived(message=msg))

    def _on_disconnect(self, event):
        self._status ='disconnected'
        self.fire(Disconnected())

    @on_event(Connecting)
    def _on_connecting(self, event):
        self._status ='connecting'

    @on_event(Connected)
    def _on_connected(self, event):
        self._status ='connected'

    @on_event(ConnectionError)
    def _on_connecting_error(self, event):
        self._status ='disconnected'

    def _on_register(self, iq):
        resp = self.xmpp.Iq()
        resp['type'] = 'set'
        resp['register']['username'] = self.xmpp.boundjid.user
        resp['register']['password'] = self.xmpp.password

        try:
            resp.send(now=True)
            logging.info("Account created for %s" % self.xmpp.boundjid)
        except IqError as e:
            logging.warning("Could not register account: %s"
                            % e.iq['error']['text'])
        except IqTimeout:
            logging.error("No response from server.")
            self.disconnect()
