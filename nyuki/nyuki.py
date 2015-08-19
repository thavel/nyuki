import json
import signal
import logging
import logging.config

from nyuki.handlers import MetaHandler, on_event
from nyuki.bus import Bus
from nyuki.events import Event
from nyuki.capabilities import Exposer
from nyuki.commands import parse_init, exhaustive_config


log = logging.getLogger(__name__)


class Nyuki(metaclass=MetaHandler):
    """
    A lightweigh base class to build nyukis. A nyuki provides tools that shall
    help the developer with managing the following topics:
      - Bus of communication between nyukis.
      - Asynchronous events.
      - Capabilities exposure through a REST API.
    This class has been written to perform the features above in a reliable,
    single-threaded, asynchronous and concurrent-safe environment.
    The core engine of a nyuki implementation is the asyncio event loop (a
    single loop is used for all features). A wrapper is also provide to ease the
    use of asynchronous calls over the actions nyukis are inteded to do.
    """
    def __init__(self, conf=None):
        self._config = exhaustive_config(conf or parse_init())
        logging.config.dictConfig(self._config['log'])

        self._bus = Bus(**self._config['bus'])
        self._exposer = Exposer(self.event_loop.loop)

    @property
    def config(self):
        return self._config

    @property
    def event_loop(self):
        return self._bus.loop

    @property
    def capabilities(self):
        return self._exposer.capabilities

    @property
    def event_manager(self):
        return self._bus.event_manager

    @property
    def capability_exposer(self):
        return self._exposer

    @property
    def send(self):
        return self._bus.send

    @on_event(Event.Connected)
    def _on_connection(self):
        log.info("Nyuki connected to the bus")

    @on_event(Event.Disconnected, Event.ConnectionError)
    def _on_disconnection(self, event=None):
        """
        The direct result of a disconnection from the bus is the shut down of
        the event loop (that eventually makes the nyuki process to exit).
        """
        # Might need a bit of retry here before exiting...
        self.event_loop.stop()
        log.info("Nyuki exiting")

    def start(self):
        """
        Start the nyuki: launch the bus client and expose capabilities.
        Basically, it starts the event loop.
        """
        signal.signal(signal.SIGTERM, self.abort)
        signal.signal(signal.SIGINT, self.abort)
        self._bus.connect()
        self._exposer.expose(**self._config['api'])
        self.event_loop.start(block=True)

    def abort(self, signum=signal.SIGINT, frame=None):
        """
        Signal handler: gracefully stop the nyuki.
        """
        log.warning("Caught signal {}".format(signum))
        self.stop()

    def stop(self, timeout=5):
        """
        Stop the nyuki. Basically, disconnect to the bus. That will eventually
        trigger a `Disconnected` event.
        """
        self._exposer.shutdown()
        self._bus.disconnect(timeout=timeout)
