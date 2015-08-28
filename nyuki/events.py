from enum import Enum

import logging


log = logging.getLogger(__name__)


def on_event(*events):
    """
    Nyuki method decorator to register a callback for a bus event.
    """
    def call(func):
        func.on_event = set(events)
        return func
    return call


class Event(Enum):
    """
    Bus events that can be trigger upon reception of an XMPP event.
    """
    Connecting = 'connecting'
    Connected = 'connected'
    ConnectionError = 'connection_error'
    Disconnected = 'disconnected'
    EventReceived = 'event_received'


class EventManager(object):
    """
    Manager that helps to perform asynchronous callbacks when a bus event is
    triggered. This class use our asyncio event loop wrapper EventLoop.
    """
    def __init__(self, loop):
        self._loop = loop
        self._callbacks = self._init_callbacks()
        log.debug("Available events: {}".format(list(Event)))
        log.debug("Events will be called through {}".format(self._loop.loop))

    @staticmethod
    def _init_callbacks():
        """
        Build the main data structure with available events.
        """
        callbacks = dict()
        for event in Event:
            callbacks[event] = set()
        return callbacks

    def register(self, event, callback):
        """
        Add a callback for a given event.
        """
        if event not in Event:
            raise ValueError("Event {} does not exist".format(event))
        self._callbacks[event].add(callback)
        log.debug("Callback added for {} event".format(event.name))

    def trigger(self, event, *args):
        """
        Perform all registered callbacks for the triggered event.
        """
        if event not in self._callbacks:
            raise ValueError("Event {} is not registered".format(event))
        for callback in self._callbacks[event]:
            self._loop.async(callback, *args)
        log.debug("{} event triggered".format(event.name))
