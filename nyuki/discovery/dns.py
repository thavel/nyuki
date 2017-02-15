import asyncio
import logging
from aiodns import DNSResolver
from aiodns.error import DNSError

from nyuki.discovery import DiscoveryService


log = logging.getLogger(__name__)


class DnsDiscovery(DiscoveryService):

    SCHEME = 'dns'
    CONF_SCHEMA = {
        "type": "object",
        "properties": {
            "discovery": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["dns"]},
                    "entry": {"type": "string", "minLength": 1},
                    "period": {"type": "integer", "minimum": 1}
                },
                "additionalProperties": False
            }
        }
    }

    _RETRY_PERIOD = 5

    def __init__(self, nyuki, loop=None):
        self._nyuki = nyuki
        self._entry = None
        self._period = None
        self._future = None
        self._callbacks = []
        self._resolver = DNSResolver(loop=loop or asyncio.get_event_loop())

        self._nyuki.register_schema(self.CONF_SCHEMA)

    def configure(self, entry=None, period=2, **kwargs):
        self._entry = entry or self._nyuki.config['service']
        self._period = period

    def register(self, callback):
        if not callable(callback) or callback in self._callbacks:
            raise ValueError('Invalid or already registered callback')
        self._callbacks.append(callback)

    async def start(self, *args, **kwargs):
        self._future = asyncio.ensure_future(self.periodic_query())

    async def periodic_query(self):
        while True:
            try:
                answers = await self._resolver.query(self._entry, 'A')
            except DNSError as exc:
                log.error("DNS query failed for discovery service")
                log.debug("DNS failure reason: %s", str(exc))
                await asyncio.sleep(self._RETRY_PERIOD)
                continue
            addresses = [record.host for record in answers]

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
