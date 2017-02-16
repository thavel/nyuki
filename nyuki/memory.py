import asyncio
import logging
from socket import error as SocketError
from aioredis import create_reconnecting_redis, RedisError

from nyuki.services import Service


log = logging.getLogger(__name__)


def memsafe(coro):
    async def wrapper(*args, **kwargs):
        try:
            return await coro(*args, **kwargs)
        except RedisError as exc:
            # Any connection and protocol related issues but also invalid
            # Redis-command formatting (not likely).
            log.exception(exc)
        except SocketError:
            log.error("Connection with Redis has been lost. Retrying...")
    return wrapper


class Memory(Service):

    def __init__(self, nyuki):
        self.store = None
        self.config = {}
        self.service = nyuki.config['service']
        self.loop = nyuki.loop or asyncio.get_event_loop()

    @property
    def available(self):
        return self.store is not None

    def key(self, instance, *args):
        keyspace = '{}.{}'.format(self.service, instance)
        for arg in args:
            keyspace = '{}.{}'.format(keyspace, arg)
        return keyspace

    def configure(self, *args, **kwargs):
        self.config = kwargs

    async def start(self, *args, **kwargs):
        """
        Setup a shared memory using Redis.
        """
        self.store = await create_reconnecting_redis(
            (
                self.config.get('host', 'localhost'),
                self.config.get('port', 6379)
            ),
            db=self.config.get('database', 0),
            ssl=self.config.get('ssl'),
            loop=self.loop
        )

        try:
            # An initial 'ping' command allows to immediately check the
            # connection health.
            await self.store.ping()
            log.info("Connection made with Redis")
        except (RedisError, SocketError) as exc:
            log.error("Fail to connect to Redis")
            log.exception(exc)

    async def stop(self, *args, **kwargs):
        pass
