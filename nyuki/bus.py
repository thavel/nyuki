import logging
from slixmpp import ClientXMPP
from slixmpp.exceptions import IqError, IqTimeout, XMPPError
from slixmpp.xmlstream import JID

from nyuki.events import EventManager, Event
from nyuki.loop import EventLoop
from nyuki.xep_nyuki import XEP_Nyuki


log = logging.getLogger(__name__)


class _BusClient(ClientXMPP):
    """
    XMPP client to connect to the bus.
    This class is based on Slixmpp (fork of Sleexmpp) using asyncio event loop.
    """

    def __init__(self, jid, password, host=None, port=None):

        jid = JID(jid)
        if not host and not jid.user:
            raise XMPPError('Wrong JID format given (use user@host/nyuki)')
        jid.resource = 'nyuki'

        super().__init__(jid, password)

        host = host or jid.domain
        self._address = (host, port or 5222)

        self.register_plugin('xep_0045')  # Multi-user chat
        self.register_plugin('xep_0133')  # Service administration
        self.register_plugin('xep_0077')  # In-band registration
        self.register_plugin('xep_nyuki', module=XEP_Nyuki)  # Nyuki requests

        # Disable IPv6 util we really need it
        self.use_ipv6 = False

    def connect(self, **kwargs):
        """
        Schedule the connection process.
        """
        super().connect(address=self._address, **kwargs)


class Bus(object):

    """
    Provide methods to perform communication over the bus.
    Events are handled by the EventManager.
    """

    RESPONSE_TIMEOUT = 60

    def __init__(self, jid, password, host=None, port=None, room=None):
        self.client = _BusClient(jid, password, host, port)
        self.client.add_event_handler('connecting', self._on_connection)
        self.client.add_event_handler('register', self._on_register)
        self.client.add_event_handler('session_start', self._on_start)
        self.client.add_event_handler('disconnected', self._on_disconnect)
        self.client.add_event_handler('connection_failed', self._on_failure)
        self.client.add_event_handler('nyuki_request', self._on_request)
        self.client.add_event_handler('nyuki_response', self._on_response)

        # Wrap asyncio loop for easy usage
        self._loop = EventLoop(loop=self.client.loop)
        self._event = EventManager(self._loop)

        # The application MUC
        self.room = '{}@applications.localhost'.format(room) if room else None

    @property
    def loop(self):
        return self._loop

    @property
    def nick(self):
        return self.client.boundjid.user

    @property
    def event_manager(self):
        return self._event

    def _on_connection(self, event):
        """
        XMPP event handler while starting the authentication to the server.
        Also trigger a bus event: `Connecting`.
        """
        log.debug("Connecting to the bus")
        self._event.trigger(Event.Connecting)

    def _on_register(self, event):
        """
        XMPP event handler while registering a user (in-band registration).
        Does not trigger bus event (internal behavior), except if it fails.
        """
        def done(future):
            try:
                future.result()
            except IqError as exc:
                error = exc.iq['error']['text']
                log.debug("Could not register account: {}".format(error))
            except IqTimeout:
                log.error("No response from the server")
                self._event.trigger(Event.ConnectionError)
            finally:
                log.debug("Account {} created".format(self.client.boundjid))

        resp = self.client.Iq()
        resp['type'] = 'set'
        resp['register']['username'] = self.client.boundjid.user
        resp['register']['password'] = self.client.password
        future = resp.send()
        future.add_done_callback(done)

    def _on_start(self, event):
        """
        XMPP event handler when the connection has been made.
        Also trigger a bus event: `Connected`.
        """
        self.client.send_presence()
        self.client.get_roster()
        if self.room:
            self.client.plugin['xep_0045'].joinMUC(self.room, self.nick)
            log.debug(
                'Entered room {} with nick {}'.format(self.room, self.nick))
        log.debug('Connection to the bus succeed')
        self._event.trigger(Event.Connected)

    def _on_disconnect(self, event):
        """
        XMPP event handler when the client has been disconnected.
        Also trigger a bus event: `Disconnected`.
        """
        log.debug("Disconnected from the bus")
        self._event.trigger(Event.Disconnected)

    def _on_failure(self, event):
        """
        XMPP event handler when something is going wrong with the connection.
        Also trigger a bus event: `ConnectionError`.
        """
        log.error("Connection to the bus has failed")
        self._event.trigger(Event.ConnectionError, event)
        self.client.abort()

    def _on_request(self, iq):
        """
        XMPP event handler when a Nyuki Request has been received.
        Also trigger a bus event `RequestReceived`.
        """
        log.debug('Request received: {}'.format(iq))

        def response_callback(future):
            # Fetch returned Response object from a capability and send it.
            response = future.result()
            if response:
                status, body = response.bus_message
                self.reply(iq, status, body)

        request = iq['request']
        event = (request['capability'], request['body'], response_callback)
        self._event.trigger(Event.RequestReceived, event)

    def _on_response(self, iq):
        """
        XMPP event handler when a Nyuki Response has been received.
        Also trigger a bus event `ResponseReceived`.
        """
        log.debug('Response received: {}'.format(iq))
        event = iq['response']
        self._event.trigger(Event.ResponseReceived, event)

    def connect(self):
        """
        Connect to the XMPP server and init pluggins.
        """
        self.client.connect()
        self.client.init_plugins()

    def disconnect(self, timeout=5):
        """
        Disconnect to the XMPP server.
        Abort after a timeout (in seconds) if the action is too long.
        """
        self.client.disconnect(wait=timeout)

    def send(self, message, to, capability, callback=None):
        """
        Send a unicast message through the bus.
        """
        log.debug('Sending {} to {}'.format(message, to))
        req = self.client.Iq()
        req['type'] = 'set'
        req['request']['capability'] = capability
        req['request']['body'] = message

        if self.room:
            req['to'] = '{}/{}'.format(self.room, to)
        else:
            req['to'] = '{}/{}'.format(to, self.client.boundjid.resource)

        log.debug(req)
        req.send(callback=callback)

    def send_all(self, message, capability='process', callback=None):
        """
        Send a unicast message independently to each nyuki in the room.
        TODO: A muc seems to not understand xep_nyuki stanzas, hence is not
        able to broadcast a single message to each nyuki itself.
        """
        if not self.room:
            log.error('Trying to send to an non-existant room')
            return

        for user in self.client.plugin['xep_0045'].rooms[self.room]:
            if user != self.nick:
                self.send(message, user, capability, callback)

    def reply(self, request, status, body=None):
        """
        Send a response to a message through the bus.
        """
        log.debug('Replying {} - {} to {}'.format(
            status, body, request['from']))
        resp = request.reply()
        resp['response']['status'] = status
        resp['response']['body'] = body
        log.debug(resp)
        resp.send()
