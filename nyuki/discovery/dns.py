import asyncio
import logging
from dns import resolver
from dns.exception import DNSException

from . import DiscoveryService


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

    _RETRY_PERIOD = 3

    def __init__(self, nyuki, loop=None):
        self._nyuki = nyuki
        self._loop = loop or asyncio.get_event_loop()
        self._namedentry = None
        self._period = None
        self._future = None
        self._callbacks = []

    def configure(self, namedentry=None, period=5, **kwargs):
        self._namedentry = namedentry or self._nyuki.config['name']
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
                answers = resolver.query(self._namedentry, 'A')
            except DNSException as exc:
                log.error("DNS query failed for discovery service")
                log.debug("DNS failure reason: %s", str(exc))
                await asyncio.sleep(self._RETRY_PERIOD)
                continue

            addresses = [ip.address for ip in answers]
            log.debug(
                "Found {} instances of {}: {}",
                len(addresses), self._namedentry, addresses
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
