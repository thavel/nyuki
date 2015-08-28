import aiohttp
import asyncio
from functools import partial
import json
import logging
from slixmpp import ClientXMPP
from slixmpp.exceptions import IqError, IqTimeout

from nyuki.events import EventManager, Event
from nyuki.loop import EventLoop


log = logging.getLogger(__name__)


class _BusClient(ClientXMPP):
    """
    XMPP client to connect to the bus.
    This class is based on Slixmpp (fork of Sleexmpp) using asyncio event loop.
    """

    def __init__(self, jid, password, host=None, port=None):
        super().__init__(jid, password)

        host = host or self.boundjid.domain
        self._address = (host, port or 5222)

        self.register_plugin('xep_0045')  # Multi-user chat
        self.register_plugin('xep_0077')  # In-band registration

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

    MUC_SERVER = 'mucs.localhost'

    def __init__(self, jid, password, host=None, port=None, loop=None):
        if not isinstance(loop, EventLoop):
            log.error('loop must be an EventLoop object')
            raise TypeError

        self._loop = loop

        self.client = _BusClient(jid, password, host, port)
        self.client.loop = self._loop.loop
        self.client.add_event_handler('connection_failed', self._on_failure)
        self.client.add_event_handler('disconnected', self._on_disconnect)
        self.client.add_event_handler('groupchat_invite', self._on_invite)
        self.client.add_event_handler('groupchat_message', self._on_event)
        self.client.add_event_handler('register', self._on_register)
        self.client.add_event_handler('session_start', self._on_start)

        self.event_manager = EventManager(self._loop)

        self._topic = self.client.boundjid.user
        self._mucs = self.client.plugin['xep_0045']

    def _muc_address(self, topic):
        return '{}@{}'.format(topic, self.MUC_SERVER)

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
                self.event_manager.trigger(Event.ConnectionError)
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
        log.debug('Connection to the bus succeed')
        self.event_manager.trigger(Event.Connected)

    def _on_disconnect(self, event):
        """
        XMPP event handler when the client has been disconnected.
        Also trigger a bus event: `Disconnected`.
        """
        log.debug("Disconnected from the bus")
        self.event_manager.trigger(Event.Disconnected)

    def _on_failure(self, event):
        """
        XMPP event handler when something is going wrong with the connection.
        Also trigger a bus event: `ConnectionError`.
        """
        log.error("Connection to the bus has failed")
        self.event_manager.trigger(Event.ConnectionError, event)
        self.client.abort()

    def _on_invite(self, event):
        """
        Enter room on invitation.
        """
        self.subscribe(event['from'])

    def _on_event(self, event):
        """
        XMPP event handler when a Nyuki Event has been received.
        Fire EventReceived with (from, body).
        """
        log.debug('Event received: {}'.format(event))
        event = (event['from'], json.loads(event['body']))
        self.event_manager.trigger(Event.EventReceived, event)

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

    def publish(self, message):
        """
        Send an event on nyuki's topic muc.
        """
        if not isinstance(message, dict):
            log.error('Message must be a dict')
            return

        if self._muc_address(self._topic) not in self._mucs.rooms:
            self.subscribe(self._topic)

        log.debug('Publishing {} to {}'.format(message, self._topic))
        msg = self.client.Message()
        msg['type'] = 'groupchat'
        msg['to'] = self._muc_address(self._topic)
        msg['body'] = json.dumps(message)
        msg.send()

    def subscribe(self, topic):
        """
        Enter into a new room using xep_0045.
        Room format must be '{name}@applications.localhost'
        """
        self._mucs.joinMUC(self._muc_address(topic), self._topic)
        log.info('Subscribed to "{}"'.format(topic))

    @asyncio.coroutine
    def _request(self, url, method, data=None):
        """
        Asynchronously send a request to method/url.
        """
        if isinstance(data, dict):
            data = json.dumps(data)
        headers = {'Content-Type': 'application/json'}
        response = yield from aiohttp.request(
            method, url, data=data, headers=headers)
        status = response.status
        try:
            body = yield from response.json()
        except ValueError:
            log.error('Response was not a json')
            body = {}
        return (status, body)

    def _handle_response(self, callback, future):
        """
        Check the response of a request using its Future object.
        Also call asynchronously the response callback, if given.
        """
        try:
            status, body = future.result()
        except (aiohttp.HttpProcessingError,
                aiohttp.ServerDisconnectedError,
                aiohttp.ClientOSError) as exc:
            log.exception(exc)
            log.error('Failed to send request')
            return

        if callback:
            log.info('Calling response callback with ({}, {})'.format(
                     status, body))
            self._loop.async(callback, status, body)

    def request(self, nyuki, endpoint, method, data=None, callback=None):
        """
        Send a P2P request to another nyuki, async a callback if given.
        The callback is called with two args 'status' and 'body' (json).
        """
        if nyuki:
            endpoint = 'http://localhost:8080/{}/api/'.format(nyuki)
        future = asyncio.async(self._request(endpoint, method, data))
        future.add_done_callback(partial(self._handle_response, callback))
