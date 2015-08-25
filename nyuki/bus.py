from asyncio import Future
import logging
from slixmpp import ClientXMPP
from slixmpp.exceptions import IqError, IqTimeout, XMPPError
from slixmpp.xmlstream import JID
from slixmpp.xmlstream.handler import Callback
from slixmpp.xmlstream.matcher import MatcherId
from uuid import uuid4

from nyuki.events import EventManager, Event
from nyuki.loop import EventLoop
from nyuki.xep_nyuki import XEP_Nyuki


log = logging.getLogger(__name__)


class RequestError(XMPPError):
    def __init__(self, message):
        super().__init__()
        self.message = message


class TimeoutError(XMPPError):
    def __init__(self, message):
        super().__init__(condition='request-response-timeout', etype='cancel')
        self.message = message


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
    MUC_SERVER = 'mucs.localhost'

    def __init__(self, jid, password, host=None, port=None, rooms=None):
        self.client = _BusClient(jid, password, host, port)
        self.client.add_event_handler('connecting', self._on_connection)
        self.client.add_event_handler('register', self._on_register)
        self.client.add_event_handler('session_start', self._on_start)
        self.client.add_event_handler('disconnected', self._on_disconnect)
        self.client.add_event_handler('connection_failed', self._on_failure)
        self.client.add_event_handler('groupchat_invite', self._on_invite)
        self.client.add_event_handler('nyuki_request', self._on_request)
        self.client.add_event_handler('nyuki_event', self._on_event)

        # Wrap asyncio loop for easy usage
        self._loop = EventLoop(loop=self.client.loop)
        self._event = EventManager(self._loop)

        # Statup MUCs
        self.rooms = rooms or list()

    @property
    def loop(self):
        return self._loop

    @property
    def nick(self):
        return self.client.boundjid.user

    @property
    def event_manager(self):
        return self._event

    @property
    def mucs(self):
        return self.client.plugin['xep_0045']

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
        for room in self.rooms:
            room = '{}@{}'.format(room, self.MUC_SERVER)
            self.enter_room(room)
        self.rooms = None
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

    def _on_invite(self, event):
        """
        Enter room on invitation.
        """
        self.enter_room(event['from'])

    def _on_request(self, message):
        """
        XMPP event handler when a Nyuki Request has been received.
        Also trigger a bus event `RequestReceived`.
        """
        log.debug('Request received: {}'.format(message))

        def response_callback(future):
            # Fetch returned Response object from a capability and send it.
            response = future.result()
            if response:
                status, body = response.bus_message
                self.reply(message, status, body)

        request = message['request']
        event = (request['capability'], request['json'], response_callback)
        self._event.trigger(Event.RequestReceived, event)

    def _on_event(self, event):
        """
        XMPP event handler when a Nyuki Event has been received.
        """
        log.debug('Event received: {}'.format(event))

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

    def enter_room(self, room):
        """
        Enter into a new room using xep_0045.
        Room format must be '{name}@applications.localhost'
        """
        self.mucs.joinMUC(room, self.nick)
        log.debug('Entered room {} with nick {}'.format(room, self.nick))

    def _send_with_callback(self, message, callback):
        """
        Send a bus message, waiting for a matching ID response to trigger
        the given callback.
        """
        future = Future()
        matcher = MatcherId(message['id'])

        timeout_name = 'RequestTimeout_{}'.format(message['id'])
        handler_name = 'RequestCallback_{}'.format(message['id'])

        def callback_success(result):
            if result['type'] == 'error':
                future.set_exception(RequestError(result))
            else:
                future.set_result(result)

            self.client.cancel_schedule(timeout_name)

            if callback is not None:
                callback(result)

        def callback_timeout():
            future.set_exception(TimeoutError(message))
            self.client.remove_handler(handler_name)
            log.info('No longer waiting for a response')
            log.debug('cancel response handler id {}'.format(message['id']))

        self.client.schedule(
            timeout_name,
            self.RESPONSE_TIMEOUT,
            callback_timeout,
            repeat=False)

        handler = Callback(
            handler_name, matcher, callback_success, once=True)
        self.client.register_handler(handler)

        message.send()
        return future

    def send(self, message, to, capability, callback=None):
        """
        Send a unicast message through the bus.
        """
        log.debug('Sending {} to {}'.format(message, to))
        msg = self.client.Message()
        msg['type'] = 'message'
        msg['to'] = '{}/{}'.format(to, self.client.boundjid.resource)
        msg['id'] = str(uuid4())
        msg['request']['capability'] = capability
        msg['request']['json'] = message
        self._send_with_callback(msg, callback)

    def send_to_room(self, message, room):
        """
        Send a unicast message independently to each nyuki in the room.
        TODO: A muc seems to not understand xep_nyuki stanzas, hence is not
        able to broadcast a single message to each nyuki itself.
        """
        room = '{}@{}'.format(room, self.MUC_SERVER)
        if room not in self.mucs.rooms:
            log.error('Trying to send to an unknown room : %s', room)
            return

        log.debug('Sending {} to room {}'.format(message, room))
        msg = self.client.Message()
        msg['type'] = 'groupchat'
        msg['to'] = room
        msg['event']['json'] = message
        msg.send()

    def reply(self, request, status, body=None):
        """
        Send a response to a message through the bus.
        """
        log.debug('Replying {} - {} to {}'.format(
            status, body, request['from']))
        resp = request.reply()
        resp['id'] = request['id']
        resp['response']['json'] = body
        resp['response']['status'] = str(status)
        log.debug(resp)
        resp.send()
