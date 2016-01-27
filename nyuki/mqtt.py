import asyncio
from hbmqtt.client import MQTTClient, ClientException, ConnectException
from hbmqtt.errors import NoDataException
from hbmqtt.mqtt.constants import QOS_2
import json
import logging
import re
from uuid import uuid4

from nyuki.services import Service


log = logging.getLogger(__name__)


class Request(object):

    def __init__(self, nyuki, capability, uuid):
        pass


class ReMQTTClient(MQTTClient):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # We handle that ourselves
        self.config['auto_reconnect'] = False


class MqttBus(Service):

    """
    Nyuki topics formatted as:
        - global publications:
            {nyuki_name}/publications
        - request/response:
            {nyuki_name}/{capability_name}/{request_id}/<request|response>
    """

    def __init__(self, nyuki):
        self._nyuki = nyuki
        self._loop = nyuki.loop or asyncio.get_event_loop()
        self._host = None
        self._self_topic = None
        self._request_topic = None
        self.client = ReMQTTClient(loop=self._loop)
        self._pending = {}
        self._subscriptions = {}

        # Coroutines
        self._frun = None

    def configure(self, host, name):
        self._host = host
        self._name = name
        self._self_topic = '{}/publications'.format(self._name)
        self._request_topic = '{}/+/+/request'.format(self._name)

    async def start(self):
        self._frun = asyncio.ensure_future(self._run(), loop=self._loop)

    async def stop(self):
        # Clean tasks
        for task in self.client.client_tasks:
            log.debug('cancelling mqtt client tasks')
            task.cancel()
        if self._frun:
            log.debug('cancelling _run coroutine')
            self._frun.cancel()
        if self.client._connected_state.is_set():
            log.debug('disconnecting mqtt client')
            await self.client.disconnect()
        log.info('MQTT service stopped')

    def _publish_topic(self, nyuki):
        return '{}/publications'.format(nyuki)

    def _resp_topic_from_req(self, req_topic):
        return req_topic.replace('/request', '/response')

    async def _sub(self, topic, callback):
        log.debug('MQTT subscription to %s', topic)
        await self.client.subscribe([(topic, QOS_2)])

        if not asyncio.iscoroutinefunction(callback):
            log.warning('event callback must be a coroutine')
            callback = asyncio.coroutine(callback)
        self._subscriptions[topic] = callback

    async def _unsub(self, topic):
        log.debug('MQTT unsubscription from %s', topic)
        await self.client.unsubscribe([topic])
        if topic in self._subscriptions:
            del self._subscriptions[topic]

    async def subscribe(self, nyuki, callback):
        log.info('Subscribing to %s', nyuki)
        topic = self._publish_topic(nyuki)
        await self._sub(topic, callback)

    async def unsubscribe(self, nyuki):
        log.info('Unsubscribing from %s', nyuki)
        topic = self._publish_topic(nyuki)
        await self._unsub(topic)

    async def publish(self, data, topic=None):
        topic = topic or self._self_topic
        log.info('Publishing into %s', topic)
        data = json.dumps(data)
        log.debug('dump: %s', data)
        # Implies QOS_0
        await self.client.publish(topic, data.encode())

    async def request(self, nyuki, capability, data):
        req_topic = '{}/{}/{}/request'.format(nyuki, capability, str(uuid4())[:8])
        resp_topic = self._resp_topic_from_req(req_topic)
        future = asyncio.Future()
        self._pending[resp_topic] = future

        async def cb(data):
            future.set_result(data)

        # Subscribe to the request response
        await self._sub(resp_topic, cb)
        # Publish the request
        await self.publish(data, req_topic)

        # Wait for the response
        await future

        # Retrieve the response and unsubscribe
        response = future.result()
        del self._pending[resp_topic]
        await self._unsub(resp_topic)

        log.info('Response received: %s', response)
        return response

    async def reply(self, topic, data):
        resp_topic = self._resp_topic_from_req(topic)
        if not resp_topic.endswith('/response'):
            log.error('Reply failure: %s', resp_topic)
            return
        await self.publish(data, resp_topic)

    async def _run(self):
        """
        Handle reconnection every (last * 2) + 1 seconds
        """
        delay = 1
        while True:
            try:
                log.info('Trying MQTT connection to %s', self._host)
                try:
                    await self.client.connect(self._host, cafile='ssl/ca.crt')
                except (ConnectException, NoDataException) as e:
                    log.error(e)
                    current_delay = (delay * 2) + 1
                    log.info('Waiting %d seconds to reconnect', current_delay)
                    await asyncio.sleep(current_delay)
                    delay = current_delay
                    continue

                # Reset reconnection delay
                delay = 1
                log.info('Connection made with MQTT')
                # Subscribe to own requests topic
                await self._sub(self._request_topic, self._handle_request)

                try:
                    await self._listen()
                except ClientException as e:
                    log.error(e)

            except asyncio.CancelledError:
                log.debug('Connection loop cancelled')
                break

    async def _listen(self):
        while True:
            message = await self.client.deliver_message()
            topic = message.topic

            # Ignore own message
            if topic == self._publish_topic(self._name):
                return

            # Check subscription event
            if topic in self._subscriptions:
                asyncio.ensure_future(self._handle_event(message), loop=self._loop)
            # Check request
            elif re.match(r'^%s/\w+/\w{8}/request$' % self._name, topic):
                asyncio.ensure_future(self._handle_request(message), loop=self._loop)
            else:
                log.debug('Unknown event received on topic: %s', topic)

    async def _handle_event(self, message):
        """
        Handle an event from a subscribed topic
        """
        data = json.loads(message.data.decode())
        log.info("Event from topic '%s'", message.topic)
        log.debug('dump: %s', data)

        callback = self._subscriptions[message.topic]
        await callback(data)

    async def _handle_request(self, message):
        """
        Dispatch either a request or a response
        """
        # Check topic validity
        m = re.match(
            r'^(?P<nyuki_name>\w+)/'
            r'(?P<capability>\w+)/'
            r'(?P<uuid>\w{8})/'
            r'(?P<mtype>\w+)$',
            message.topic
        )
        if not m:
            log.debug('Topic did not match: %s', message.topic)
            return

        data = json.loads(message.data.decode())
        log.info("Message from topic '%s'", message.topic)
        log.debug('dump: %s', data)

        if m.group('mtype') == 'response' and message.topic in self._pending:
            # Is a pending response, set future result
            self._pending[message.topic].set_result(data)
        elif m.group('mtype') == 'request':
            # Is a request
            resp = await self._nyuki.api.call(m.group('capability'), data)
            await self.reply(message.topic, resp)
        else:
            log.error('Message type does not match: %s', m.group('mtype'))
