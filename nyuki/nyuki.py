import signal
import logging
import logging.config

from nyuki.handlers import MetaHandler
from nyuki.bus import Bus
from nyuki.events import Event, on_event
from nyuki.capabilities import Exposer
from nyuki.commands import (
    build_args, read_conf_json, write_conf_json, update_config
)


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
    The core engine of a nyuki implementation is the asyncio event loop
    (a single loop is used for all features).
    A wrapper is also provide to ease the use of asynchronous calls
    over the actions nyukis are inteded to do.
    """
    def __init__(self, args=None):
        args = args or build_args()
        self.config_filename = args.config
        self.load_config(args)
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

    @on_event(Event.RequestReceived)
    def _handle_request(self, event):
        """
        Handle request received from the bus.
        Call the targeted capability.
        """
        capa_name, request, response_callback = event
        future = self._exposer.call(capa_name, request)
        if future:
            future.add_done_callback(response_callback)

    @on_event(Event.ResponseReceived)
    def _handle_response(self, response):
        """
        Handle response for a request sent through the bus.
        """
        log.debug("Response received, but ignored")

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

    def load_config(self, args):
        self._config = read_conf_json(self.config_filename, args)

    def save_config(filename=None):
        write_conf_json(self.config, filename or self.config_filename)

    def update_config(self, value, path):
        update_config(self._config, value, path)
