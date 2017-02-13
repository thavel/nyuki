import pickle
import asyncio
import logging
from socket import error as SocketError
from aioredis import create_reconnecting_redis, RedisError


log = logging.getLogger(__name__)


def handle_errors(coro):
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


class Memory(object):

    def __init__(self, *, loop=None):
        self.store = None
        self.service = None
        self.loop = loop or asyncio.get_event_loop()

    @property
    def available(self):
        return self.store is not None

    def key(self, resource, entry):
        return '{service}.workflows.{resource}.{entry}'.format(
            service=self.service,
            resource=resource,
            entry=entry
        )

    async def setup(self, nyuki_config):
        """
        Setup a shared memory using Redis.
        """
        config = nyuki_config.get('redis')

        if not config:
            self.store = None
            return

        self.service = nyuki_config.get('service')
        if not self.service:
            log.error("Can't start Redis: 'service' config key is missing")
            return

        self.store = await create_reconnecting_redis(
            (config.get('host', 'localhost'), config.get('port', 6379)),
            db=config.get('database', 0),
            ssl=config.get('ssl'),
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

    @handle_errors
    async def clear_report(self, uid):
        key = self.key('instances', uid)
        await self.store.delete(key)

    @handle_errors
    async def write_report(self, report, replace=True):
        """
        Store an instance report into shared memory.
        A simple 'set' is used againts a 'hset' (hash storage), even though the
        'hset' seems more appropriate, because a field in a hash can't have TTL
        """
        uid = report['exec']['id']
        response = await self.store.set(
            key=self.key('instances', uid),
            value=pickle.dumps(report),
            expire=86400,
            exist=None if replace else False
        )

        if not response:
            log.error("Can't share workflow id %s context in memory", uid)

    @handle_errors
    async def read_report(self, uid):
        key = self.key('instances', uid)
        report = await self.store.get(key)
        if not report:
            raise KeyError("Can't find workflow id context %s in memory", uid)
        return pickle.loads(report)
