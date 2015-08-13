import signal
import logging
import logging.config

from nyuki.logging import DEFAULT_LOGGING
from nyuki.bus import Bus
from nyuki.event import Event
from nyuki.capability import CapabilityExposer, Capability


log = logging.getLogger(__name__)


def on_event(event):
    """
    Nyuki method decorator to register a callback for a bus event.
    """
    def call(func):
        func.on_event = event
        return func
    return call


def capability(access, endpoint):
    """
    Nyuki method decorator to register a capability.
    It will be exposed as a HTTP route for the nyuki's API.
    """
    def call(func):
        func.capability = Capability(name=func.__name__, method=func,
                                     access=access, endpoint=endpoint)
        return func
    return call


class CapabilityHandler(type):
    def __call__(cls, *args, **kwargs):
        """
        Register decorated method to be routed by the web app.
        """
        nyuki = super().__call__(*args, **kwargs)
        for capa in cls._filter_capability(nyuki):
            nyuki.capability_exposer.register(capa)
        return nyuki

    @staticmethod
    def _filter_capability(obj):
        """
        Find methods decorated with `capability`.
        """
        for attr in dir(obj):
            value = getattr(obj, attr)
            if callable(value) and hasattr(value, 'capability'):
                yield value.capability


class EventHandler(type):
    def __call__(cls, *args, **kwargs):
        """
        Register decorated method to be called when an event is trigger.
        """
        nyuki = super().__call__(*args, **kwargs)
        for method, event in cls._filter_event(nyuki):
            nyuki.event_manager.register(event, method)
        return nyuki

    @staticmethod
    def _filter_event(obj):
        """
        Find methods decorated with `on_event`.
        """
        for attr in dir(obj):
            value = getattr(obj, attr)
            if callable(value) and hasattr(value, 'on_event'):
                yield value, value.on_event


class MetaHandler(EventHandler, CapabilityHandler):
    """
    Meta class that registers all decorated methods as either a capability or
    a callback for a bus event.
    """
    def __call__(cls, *args, **kwargs):
        nyuki = super().__call__(*args, **kwargs)
        return nyuki


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
    API_IP = '0.0.0.0'
    API_PORT = 8080

    def __init__(self):
        # Let's assume we've fetched configs through the command line/conf file
        self.config = {
            'bus': {
                'jid': 'test@localhost',
                'password': 'test',
                'host': '192.168.0.216'
            }
        }

        logging.config.dictConfig(DEFAULT_LOGGING)
        self._bus = Bus(**self.config['bus'])
        self._exposer = CapabilityExposer(self.event_loop)

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

    @on_event(Event.Connected)
    def _on_connection(self):
        log.info("Nyuki connected to the bus")

    @on_event(Event.Disconnected)
    def _on_disconnection(self):
        """
        The direct result of a disconnection from the bus is the shut down of
        the event loop (that eventually makes the nyuki process to exit).
        """
        # Might need a bit of retry here before exiting?
        self.event_loop.stop()
        log.info("Nyuki exiting")

    @on_event(Event.MessageReceived)
    def _dispatch(self, event):
        """
        Dispatch message to its capability.
        """
        capa_name = event['subject']
        self._exposer.use(capa_name, event)

    def start(self):
        """
        Start the nyuki: launch the bus client and expose capabilities.
        Basically, it starts the event loop.
        """
        signal.signal(signal.SIGTERM, self.abort)
        signal.signal(signal.SIGINT, self.abort)
        self._bus.connect()
        self._exposer.expose(self.API_IP, self.API_PORT)
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
        self._bus.disconnect(timeout=timeout)
