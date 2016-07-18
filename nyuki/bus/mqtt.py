import asyncio
from datetime import datetime
from hbmqtt.client import MQTTClient, ConnectException
from hbmqtt.errors import NoDataException
from hbmqtt.mqtt.constants import QOS_2
import json
import logging
import re
from uuid import uuid4

from nyuki.bus import reporting
from nyuki.bus.persistence import BusPersistence, EventStatus, PersistenceError
from nyuki.services import Service


log = logging.getLogger(__name__)


class MqttBus(Service):

    """
    Nyuki topics formatted as:
        - global publications:
            publications/{nyuki_name}
    """

    CONF_SCHEMA = {
        "type": "object",
        "required": ["bus"],
        "properties": {
            "bus": {
                "type": "object",
                "required": ["host", "name"],
                "properties": {
                    "certificate": {"type": "string", "minLength": 1},
                    "host": {"type": "string", "minLength": 1},
                    "name": {"type": "string", "minLength": 1},
                    "port": {"type": "integer"},
                    "persistence": {
                        "type": "object",
                        "properties": {
                            "backend": {
                                "type": "string",
                                "minLength": 1
                            }
                        }
                    },
                    "report_channel": {"type": "string", "minLength": 1},
                    "service": {"type": "string", "minLength": 1}
                },
                "additionalProperties": False
            }
        }
    }

    BASE_PUB = 'publications'
    BASE_RESP = 'responses'

    def __init__(self, nyuki, loop=None):
        self._nyuki = nyuki
        self._loop = loop or asyncio.get_event_loop()
        self._host = None
        self._self_topic = None
        self.client = MQTTClient(
            config={'auto_reconnect': False},
            loop=self._loop
        )
        self._pending = {}
        self.name = None
        self._subscriptions = {}
        self._disconnection_datetime = None

        # Coroutines
        self.connect_future = None
        self.listen_future = None

    def configure(self, host, name, port=1883, certificate=None,
                  persistence={}, report_channel='monitoring', service=None):
        self._host = '{}:{}'.format(host, port)
        self.name = name
        self._self_topic = self._publish_topic(self.name)
        self._certificate = certificate
        self._report_channel = report_channel

        # Persistence storage
        self._persistence = BusPersistence(name=name, **persistence)
        log.info('Bus persistence set to %s', self._persistence.backend)

    async def start(self):
        def cancelled(future):
            try:
                future.result()
            except asyncio.CancelledError:
                log.debug('future cancelled: %s', future)
        self.connect_future = asyncio.ensure_future(self._run())
        self.connect_future.add_done_callback(cancelled)

        try:
            await self._persistence.init()
        except PersistenceError:
            log.error(
                'Could not init persistence storage with %s',
                self._persistence.backend
            )

    async def stop(self):
        # Clean tasks
        for task in self.client.client_tasks:
            log.debug('cancelling mqtt client tasks')
            task.cancel()
        if self.connect_future:
            log.debug('cancelling _run coroutine')
            self.connect_future.cancel()
        if self.listen_future:
            log.debug('cancelling _listen coroutine')
            self.listen_future.cancel()
        if self.client._connected_state.is_set():
            log.debug('disconnecting mqtt client')
            await self.client.disconnect()
        await self._persistence.close()
        log.info('MQTT service stopped')

    def init_reporting(self):
        """
        Initialize reporting module
        """
        reporting.init(self.name, self, '{}/{}'.format(
            self._report_channel, self.name
        ))

    def _publish_topic(self, nyuki):
        return '{}/{}'.format(self.BASE_PUB, nyuki)

    async def replay(self, since=None, status=None):
        """
        Replay events since the given datetime (or all if None)
        """
        log.info('Replaying events')
        if since:
            log.info('    since %s', since)
        if status:
            log.info('    with status %s', status)

        events = await self._persistence.retrieve(since, status)
        for event in events:
            await self.publish(json.loads(
                event['message']),
                event['topic'],
                event['id']
            )

    async def subscribe(self, topic, callback):
        """
        Subscribe to a topic and setup the callback
        """
        if not asyncio.iscoroutinefunction(callback):
            raise ValueError('event callback must be a coroutine')
        log.debug('MQTT subscription to %s', topic)
        await self.client.subscribe([(topic, QOS_2)])
        # Transform the mqtt pattern into a regex one
        regex = r'^{}$'.format(
            topic.replace('+', '[^\/]+').replace('#', '.+')
        )
        self._subscriptions[re.compile(regex)] = callback
        log.info('Callback set on regex: %s', regex)

    async def unsubscribe(self, topic):
        """
        Unsubscribe from the topic, remove callback if set
        """
        log.debug('MQTT unsubscription from %s', topic)
        await self.client.unsubscribe([topic])
        if topic in self._subscriptions:
            del self._subscriptions[topic]

    async def publish(self, data, topic=None, previous_uid=None):
        """
        Publish in given topic or default one
        """
        uid = previous_uid or str(uuid4())
        topic = topic or self._self_topic
        log.info('Publishing into %s', topic)
        data = json.dumps(data)
        log.debug('dump: %s', data)

        if not self.client._connected_state.is_set():
            status = EventStatus.PENDING
        else:
            # Implies QOS_0
            await self.client.publish(topic, data.encode())
            status = EventStatus.SENT

        if previous_uid:
            await self._persistence.update(previous_uid, status)
        elif self._persistence:
            await self._persistence.store({
                'id': uid,
                'status': status.value,
                'topic': topic,
                'message': data,
            })
            if self._persistence.memory_buffer.is_full:
                asyncio.ensure_future(self._nyuki.on_buffer_full(
                    self._persistence.memory_buffer.free_slot
                ))

    async def _run(self):
        """
        Handle reconnection every 3 seconds
        """
        while True:
            log.info('Trying MQTT connection to %s', self._host)
            try:
                await self.client.connect(
                    self._host,
                    cafile=self._certificate
                )
            except (ConnectException, NoDataException) as exc:
                log.error(exc)
                log.info('Waiting 3 seconds to reconnect')
                await asyncio.sleep(3.0)
                continue

            # Replaying events
            log.info('Connection made with MQTT')
            if self._persistence and self._disconnection_datetime:
                asyncio.ensure_future(self.replay(
                    self._disconnection_datetime,
                    EventStatus.not_sent()
                ))

            self._disconnection_datetime = None
            # Start listening
            self.listen_future = asyncio.ensure_future(self._listen())
            # Blocks until mqtt is disconnected
            await self.client._handler.wait_disconnect()
            self._disconnection_datetime = datetime.utcnow()
            # Clean listen_future
            self.listen_future.cancel()
            self.listen_future = None

    async def _listen(self):
        """
        Listen to events after a successful connection
        """
        while True:
            message = await self.client.deliver_message()
            topic = message.topic

            # Ignore own message
            if topic == self._publish_topic(self.name):
                continue

            for regex, callback in self._subscriptions.items():
                if regex.match(topic):
                    data = json.loads(message.data.decode())
                    log.debug("Event from topic '%s': %s", message.topic, data)
                    asyncio.ensure_future(callback(topic, data))
