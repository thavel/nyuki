import logging

from slixmpp import ClientXMPP
from slixmpp.exceptions import XMPPError, IqError, IqTimeout


log = logging.getLogger(__name__)


class _BusClient(ClientXMPP):

    def __init__(self, jid, password, host=None, port=None):
        super().__init__(jid, password)
        try:
            host = host or jid.split('@')[1]
        except IndexError:
            raise XMPPError("Missing argument: host")
        self._address = (host, port or 5222)

        self.register_plugin('xep_0045')  # Multi-user chat
        self.register_plugin('xep_0133')  # Service administration
        self.register_plugin('xep_0077')  # In-band registration

        self.use_ipv6 = False

    def connect(self, **kwargs):
        return super().connect(address=self._address, **kwargs)


class Bus(object):

    def __init__(self, jid, password, host=None, port=None):
        self.client = _BusClient(jid, password, host, port)
        self.client.add_event_handler('connecting', self._on_connection)
        self.client.add_event_handler('register', self._on_register)
        self.client.add_event_handler('session_start', self._on_start)
        self.client.add_event_handler('message', self._on_message)
        self.client.add_event_handler('disconnected', self._on_disconnect)
        self.client.add_event_handler('connection_failed', self._on_failure)

    @property
    def loop(self):
        return self.client.loop

    def _on_connection(self, event):
        log.info("Connecting to the bus...")

    def _on_register(self, event):
        resp = self.client.Iq()
        resp['type'] = 'set'
        resp['register']['username'] = self.client.boundjid.user
        resp['register']['password'] = self.client.password

        try:
            yield from resp.send()
        except IqError as exc:
            error = exc.iq['error']['text']
            log.warning("Could not register account: {}".format(error))
        except IqTimeout:
            log.error("No response from the server")
            self.disconnect()
        else:
            log.info("Account {} created".format(self.client.boundjid))

    def _on_start(self, event):
        self.client.send_presence()
        self.client.get_roster()
        log.info("Connection succeed")

    def _on_message(self, event):
        pass

    def _on_disconnect(self, event):
        pass

    def _on_failure(self, event):
        log.error("Connection failed")
        self.client.abort()

    def connect(self, block=False):
        self.client.connect()
        self.client.process(forever=block)

    def disconnect(self, timeout=5):
        self.client.disconnect(wait=timeout)
