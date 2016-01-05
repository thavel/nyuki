import aiohttp
import asyncio
import json
import logging
from slixmpp import ClientXMPP
from slixmpp.exceptions import IqError, IqTimeout

from nyuki.service import Service


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


class Bus(Service):

    """
    A simple class that implements Publish/Subscribe-like communications over
    XMPP. This communication layer is also called "bus".
    Each nyuki has its own "topic" (actually a MUC) to publish events. And it
    can publish events to that topic only. In the meantime, each nyuki can
    subscribe to any other topics to process events from other nyukis.
    """

    MUC_DOMAIN = 'mucs.localhost'
    CONF_SCHEMA = {
        "type": "object",
        "required": ["bus"],
        "properties": {
            "bus": {
                "type": "object",
                "required": ["jid", "password"],
                "properties": {
                    "jid": {
                        "type": "string",
                        "minLength": 1
                    },
                    "password": {
                        "type": "string",
                        "minLength": 1
                    },
                    "host": {"type": "string"},
                    "port": {"type": "integer"}
                }
            }
        }
    }

    def __init__(self, nyuki):
        self._nyuki = nyuki
        self._nyuki.register_schema(self.CONF_SCHEMA)
        self._loop = self._nyuki.loop or asyncio.get_event_loop()

        self.client = None
        self._connected = asyncio.Event()
        self._disconnected = asyncio.Event()

        self._callbacks = dict()
        self._topic = None
        self._mucs = None

    async def start(self, timeout=0):
        self._disconnected.clear()
        self.client.connect()
        if timeout:
            await asyncio.wait_for(self._connected.wait(), timeout)

    def configure(self, jid, password, host='localhost', port=5222):
        self.client = _BusClient(jid, password, host, port)
        self.client.loop = self._loop
        self.client.add_event_handler('connection_failed', self._on_failure)
        self.client.add_event_handler('disconnected', self._on_disconnect)
        self.client.add_event_handler('groupchat_message', self._on_event)
        self.client.add_event_handler('register', self._on_register)
        self.client.add_event_handler('session_start', self._on_start)
        self._topic = self.client.boundjid.user
        self._mucs = self.client.plugin['xep_0045']

    async def stop(self):
        if not self.client:
            return

        self._connected.clear()
        if not self.client.transport:
            log.warning('XMPP client is already disconnected')
            return

        self.client.disconnect(wait=2)

        try:
            await asyncio.wait_for(self._disconnected.wait(), 2.0)
        except asyncio.TimeoutError:
            log.error('Could not end bus connection after 2 seconds')

    def _muc_address(self, topic):
        return '{}@{}'.format(topic, self.MUC_DOMAIN)

    def _on_register(self, event):
        """
        XMPP event handler while registering a user (in-band registration).
        """
        def done(future):
            try:
                future.result()
            except IqError as exc:
                error = exc.iq['error']['text']
                log.debug("Could not register account: {}".format(error))
            except IqTimeout:
                log.error("No response from the server")
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
        """
        log.info('Connected to XMPP server at {}:{}'.format(
            *self.client._address
        ))
        self.client.send_presence()
        self.client.get_roster()
        # Auto-subscribe to the topic where the nyuki could publish events.
        self._connected.set()
        asyncio.ensure_future(self.subscribe(self._topic))

    def _on_disconnect(self, event):
        """
        XMPP event handler when the client has been disconnected.
        """
        log.warning('Disconnected from the bus')
        self._disconnected.set()

    def _on_failure(self, event):
        """
        XMPP event handler when something is going wrong with the connection.
        """
        log.error('Connection to XMPP server {}:{} failed'.format(
            *self.client._address
        ))
        self.client.abort()

    def _on_event(self, event):
        """
        XMPP event handler when a Nyuki Event has been received.
        Fire EventReceived with (from, body).
        """
        # ignore events from the nyuki itself
        efrom = event['from'].user
        if efrom == self.client.boundjid.user:
            return

        log.debug('event received: {}'.format(event))

        try:
            body = json.loads(event['body'])
        except ValueError:
            body = {}

        callback = self._callbacks.get(efrom)
        if callback:
            log.debug('calling callback %s', callback)
            if not asyncio.iscoroutinefunction(callback):
                log.warning('event callbacks must be coroutines')
                callback = asyncio.coroutine(callback)
            asyncio.ensure_future(callback(body))
        else:
            log.warning('No callback set for event from %s', efrom)

    def publish(self, event):
        """
        Send an event in the nyuki's own MUC so that other nyukis that joined
        the MUC can process it.
        """
        if not isinstance(event, dict):
            raise TypeError('Message must be a dict')
        log.debug(">> publishing to '{}': {}".format(self._topic, event))
        msg = self.client.Message()
        msg['type'] = 'groupchat'
        msg['to'] = self._muc_address(self._topic)
        msg['body'] = json.dumps(event)
        msg.send()

    async def subscribe(self, topic, callback=None):
        """
        Enter into a new chatroom using xep_0045.
        Room address format must be like '{topic}@mucs.localhost'
        """
        if not self._connected.is_set():
            log.info("Waiting for a connection to subscribe to '%s'", topic)
        await self._connected.wait()
        self._mucs.joinMUC(self._muc_address(topic), self._topic)
        self._callbacks[topic] = callback
        log.info("subscribed to '{}'".format(topic))

    def unsubscribe(self, topic):
        """
        Leave a chatroom.
        """
        self._mucs.leaveMUC(self._muc_address(topic), self._topic)
        del self._callbacks[topic]
        log.info("unsubscribed from '{}'".format(topic))

    async def _execute_request(self, url, method, data=None, headers=None):
        """
        Asynchronously send a request of type 'application/json' to method/url.
        If data is not None, it is supposed to be a dict.
        """
        data = json.dumps(data)
        base_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        headers = headers or {}
        headers.update(base_headers)
        log.debug('>> sending {} request to {}'.format(method.upper(), url))
        response = await aiohttp.request(
            method, url, data=data, headers=headers
        )
        try:
            data = await response.json()
        except ValueError:
            data = None
        response.json = data
        log.debug('<< received response from {}: {}'.format(url, data))
        return response

    async def request(self, nyuki, endpoint, method, out=False,
                      data=None, headers=None, callback=None):
        """
        Send a P2P request to another nyuki, async a callback if given.
        The callback is called with the response object (json).
        """
        if not out:
            endpoint = 'http://localhost:8080/{}/api/{}'.format(nyuki,
                                                                endpoint)
        try:
            response = await self._execute_request(endpoint, method,
                                                   data, headers)
        except (aiohttp.HttpProcessingError,
                aiohttp.ServerDisconnectedError,
                aiohttp.ClientOSError) as exc:
            log.error('failed to send request to {}'.format(endpoint))
            response = exc
            error = {'error': repr(exc), 'endpoint': endpoint, 'data': data}
            self.publish(error)
        if callback:
            log.debug('calling response callback with {}'.format(response))
            if asyncio.iscoroutinefunction(callback):
                asyncio.ensure_future(callback(response))
            else:
                self._loop.call_soon(callback, response)
        return response
