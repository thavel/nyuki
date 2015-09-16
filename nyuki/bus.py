import aiohttp
import asyncio
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
    def __init__(self, jid, password, host=None, port=5222):
        super().__init__(jid, password)
        host = host or self.boundjid.domain
        self._address = (host, port)

        self.register_plugin('xep_0045')  # Multi-user chat
        self.register_plugin('xep_0077')  # In-band registration

        # Disable IPv6 until we really need it
        self.use_ipv6 = False

    def connect(self, **kwargs):
        """
        Connect to the XMPP server using the default address computed at init
        if not passed as argument.
        """
        try:
            self._address = kwargs.pop('address')
        except KeyError:
            pass
        super().connect(address=self._address, **kwargs)
        self.init_plugins()


class Bus(object):
    """
    A simple class that implements Publish/Subscribe-like communications over
    XMPP. This communication layer is also called "bus".
    Each nyuki has its own "topic" (actually a MUC) to publish events. And it
    can publish events to that topic only. In the meantime, each nyuki can
    subscribe to any other topics to process events from other nyukis.
    """

    MUC_DOMAIN = 'mucs.localhost'

    def __init__(self, jid, password, host=None, port=5222, loop=None,
                 event_manager=None):
        if not isinstance(loop, EventLoop):
            raise TypeError('loop must be an EventLoop object')
        self._loop = loop
        self.client = _BusClient(jid, password, host, port)
        self.client.loop = self._loop.loop
        self.client.add_event_handler('connection_failed', self._on_failure)
        self.client.add_event_handler('disconnected', self._on_disconnect)
        self.client.add_event_handler('groupchat_invite', self._on_invite)
        self.client.add_event_handler('groupchat_message', self._on_event)
        self.client.add_event_handler('register', self._on_register)
        self.client.add_event_handler('session_start', self._on_start)

        self.event_manager = event_manager

        self._topic = self.client.boundjid.user
        self._mucs = self.client.plugin['xep_0045']

    def _muc_address(self, topic):
        return '{}@{}'.format(topic, self.MUC_DOMAIN)

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
        log.info('Connected to XMPP server {}:{}'.format(
                 *self.client._address))
        self.client.send_presence()
        self.client.get_roster()
        # Auto-subscribe to the topic where the nyuki could publish events.
        self.subscribe(self._topic)
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
        log.error("Connection to XMPP server {}:{} failed".format(
                  *self.client._address))
        self.client.abort()
        self.event_manager.trigger(Event.ConnectionError)

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
        try:
            body = json.loads(event['body'])
        except ValueError:
            body = {}
        self.event_manager.trigger(
            Event.EventReceived, event['from'], body)

    def connect(self):
        """
        Connect to the bus.
        """
        self.client.connect()

    def disconnect(self, timeout=5):
        """
        Disconnect from the bus with a default timeout set to 5s.
        """
        self.client.disconnect(wait=timeout)

    def publish(self, event):
        """
        Send an event in the nyuki's own MUC so that other nyukis that joined
        the MUC can process it.
        """
        if not isinstance(event, dict):
            raise TypeError('Message must be a dict')
        log.debug('Publishing to {}: {}'.format(self._topic, event))
        msg = self.client.Message()
        msg['type'] = 'groupchat'
        msg['to'] = self._muc_address(self._topic)
        msg['body'] = json.dumps(event)
        msg.send()

    def subscribe(self, topic):
        """
        Enter into a new chatroom using xep_0045.
        Room address format must be like '{topic}@mucs.localhost'
        """
        self._mucs.joinMUC(self._muc_address(topic), self._topic)
        log.info("Subscribed to '{}'".format(topic))

    def unsubscribe(self, topic):
        """
        Leave a chatroom.
        """
        self._mucs.leaveMUC(self._muc_address(topic), self._topic)
        log.info("Unsubscribed to '{}'".format(topic))

    @asyncio.coroutine
    def _execute_request(self, url, method, data=None, headers=None):
        """
        Asynchronously send a request to method/url.
        """
        if isinstance(data, dict):
            data = json.dumps(data)

        base_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        base_headers.update(headers or {})

        try:
            response = yield from aiohttp.request(
                method, url, data=data, headers=base_headers)
        except (aiohttp.HttpProcessingError,
                aiohttp.ServerDisconnectedError,
                aiohttp.ClientOSError) as exc:
            log.exception(exc)
            log.error('Connection with the server failed')
            status = 500
            body = {'error': 'Could not connect to the server'}
        else:
            status = response.status
            try:
                body = yield from response.json()
            except ValueError:
                log.error('Response was not a json')
                status = 406
                body = {'error': 'Could not decode JSON'}

        log.debug('received body from request : {}'.format(body))

        return (status, body)

    @asyncio.coroutine
    def request(self, nyuki, endpoint, method,
                data=None, headers=None, callback=None):
        """
        Send a P2P request to another nyuki, async a callback if given.
        The callback is called with two args 'status' and 'body' (json).
        """
        if nyuki:
            endpoint = 'http://localhost:8080/{}/api/'.format(nyuki)

        status, body = yield from self._execute_request(
            endpoint, method, data, headers)

        if callback:
            log.info('Calling response callback with ({}, {})'.format(
                     status, body))
            callback = asyncio.coroutine(callback)
            return (yield from callback(status, body))

        return (status, body)
