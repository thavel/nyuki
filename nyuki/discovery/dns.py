import asyncio
import logging
from dns import resolver

from nyuki.services import Service


log = logging.getLogger(__name__)


class DnsDiscovery(Service):

    def __init__(self, nyuki, loop=None):
        self._nyuki = nyuki
        self._loop = loop or asyncio.get_event_loop()
        self._namespace = None
        self._period = None
        self._future = None
        self._callbacks = []

    def configure(self, namespace=None, period=3, **kwargs):
        self._namespace = namespace
        self._period = period

    def register(self, callback):
        if not callable(callback) or callback in self._callbacks:
            raise ValueError('Invalid or already registered callback')
        self._callbacks.append(callback)

    async def start(self, *args, **kwargs):
        self._future = asyncio.ensure_future(self.fetch())

    async def fetch(self):
        while True:
            answers = resolver.query(self._namespace, 'A')
            addresses = [ip.address for ip in answers]
            log.debug(
                'Found {} instances of {}: {}',
                len(addresses), self._namespace, addresses
            )

            # Trigger callbacks for discovered instances IPs
            for callback in self._callbacks:
                coro = (
                    callback if asyncio.iscoroutinefunction(callback)
                    else asyncio.coroutine(callback)
                )
                asyncio.ensure_future(coro(addresses))

            # Periodically execute this method
            await asyncio.sleep(self._period)

    async def stop(self):
        self._future.cancel()
