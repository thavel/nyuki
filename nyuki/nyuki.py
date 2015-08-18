import signal
import logging
import logging.config
import asyncio
from inspect import getmembers, isclass, isfunction

from nyuki.bus import Bus
from nyuki.events import Event
from nyuki.capabilities import Exposer, Capability, HttpMethod
from nyuki.commands import parse_init, exhaustive_config


log = logging.getLogger(__name__)


def on_event(*events):
    """
    Nyuki method decorator to register a callback for a bus event.
    """
    def call(func):
        func.on_event = set(events)
        return func
    return call


def resource(endpoint, version=None):
    """
    Nyuki resource decorator to register a route.
    A resource has multiple HTTP methods (get, post, etc).
    """
    def decorated(cls):
        cls.endpoint = endpoint
        cls.version = version
        return cls
    return decorated


def capability(name=None):
    """
    Nyuki resource method decorator to register a capability.
    It will be exposed as a HTTP route for the nyuki's API.
    """
    def decorated(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper.capability = name
        return wrapper
    return decorated


class CapabilityHandler(type):
    ALLOWED_METHODS = HttpMethod.list()

    def __call__(cls, *args, **kwargs):
        """
        Register decorated resources and methods to be routed by the web app.
        """
        nyuki = super().__call__(*args, **kwargs)
        for resource, desc in cls._filter_resource(nyuki):
            version = desc.version
            endpoint = desc.endpoint
            for method, handler in cls._filter_capability(desc):
                name = handler.capability or '{}_{}'.format(method, resource)
                wrapper = cls._build_wrapper(nyuki, handler)
                nyuki.capability_exposer.register(Capability(
                    name=name.lower(),
                    method=method,
                    endpoint=endpoint,
                    version=version,
                    handler=handler,
                    wrapper=wrapper
                ))
        return nyuki

    @staticmethod
    def _build_wrapper(obj, func):
        """
        Build a wrapper method to be called by the web server.
        Route callbacks are supposed to be called through `func(request)`,
        the following code updates capabilities to be executed as instance
        methods: `func(nyuki, request)`.
        """
        return asyncio.coroutine(lambda req: func(obj, req))

    @classmethod
    def _filter_capability(mcs, resource):
        """
        Find methods decorated with `capability`.
        """
        for name, handler in getmembers(resource, isfunction):
            method = name.upper()
            if method not in mcs.ALLOWED_METHODS:
                raise ValueError("{} is not a valid HTTP method".format(method))
            if hasattr(handler, 'capability'):
                yield method, handler

    @staticmethod
    def _filter_resource(obj):
        """
        Find nested classes decorated with `endpoint`.
        """
        for name, cls in getmembers(obj, isclass):
            if hasattr(cls, 'endpoint'):
                yield name, cls


class EventHandler(type):
    def __call__(cls, *args, **kwargs):
        """
        Register decorated method to be called when an event is trigger.
        """
        nyuki = super().__call__(*args, **kwargs)
        for method, events in cls._filter_event(nyuki):
            for event in events:
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
