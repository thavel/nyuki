import signal
import logging
import logging.config

from nyuki.logging import DEFAULT_LOGGING
from nyuki.bus import Bus
from nyuki.event import Event
from nyuki.capability import CapabilityExposer, Capability


log = logging.getLogger(__name__)


def on_event(event):
    def call(func):
        func.on_event = event
        return func
    return call


def capability(method, endpoint):
    def call(func):
        func.capability = Capability(method, endpoint)
        return func
    return call


# --------------------------------------

class CapabilityHandler(type):
    pass


class EventHandler(type):
    def __call__(cls, *args, **kwargs):
        """
        Register decorated method to be called when an event is trigger.
        """
        nyuki = super().__call__(*args, **kwargs)
        for method, event in cls._filter(nyuki):
            nyuki.event_manager.register(event, method)
        return nyuki

    @staticmethod
    def _filter(obj):
        """
        Find methods decorated with `on_event`.
        """
        for attr in dir(obj):
            value = getattr(obj, attr)
            if callable(value) and hasattr(value, 'on_event'):
                yield value, value.on_event


# --------------------------------------

class MetaHandler(EventHandler, CapabilityHandler):
    def __call__(cls, *args, **kwargs):
        nyuki = super().__call__(*args, **kwargs)
        return nyuki


class Nyuki(metaclass=MetaHandler):

    API_IP = '0.0.0.0'
    API_PORT = 8080

    def __init__(self):
        # Let's assume we've fetch configs through the command line / conf file
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

    @on_event(Event.Connected)
    def _on_connection(self):
        log.info("Nyuki connected to the bus")

    def start(self):
        signal.signal(signal.SIGTERM, self.abort)
        signal.signal(signal.SIGINT, self.abort)
        self._bus.connect(block=False)
        self._exposer.expose(self.API_IP, self.API_PORT)

    def abort(self, signum=signal.SIGINT, frame=None):
        log.warning("Caught signal {}".format(signum))
        self.stop()

    def stop(self, timeout=5):
        self._bus.disconnect(timeout=timeout)
        log.info("Nyuki exiting")
