from enum import Enum

import logging


log = logging.getLogger(__name__)


class Event(Enum):
    Connecting = 'connecting'
    Connected = 'connected'
    ConnectionError = 'connection_error'
    Disconnected = 'disconnected'
    MessageReceived = 'message_received'


class EventManager(object):
    def __init__(self, loop):
        self._loop = loop
        self._callbacks = self._init_callbacks()
        log.debug("Available events: {}".format(list(Event)))

    @staticmethod
    def _init_callbacks():
        callbacks = dict()
        for event in Event:
            callbacks[event] = set()
        return callbacks

    def register(self, event, callback):
        if event not in Event:
            raise ValueError("Event {} does not exist".format(event))
        self._callbacks[event].add(callback)
        log.debug("Callback added for {} event".format(event.name))

    def trigger(self, event, *args):
        if event not in self._callbacks:
            raise ValueError("Event {} is not registered".format(event))
        for callback in self._callbacks[event]:
            self._loop.async(callback, *args)
        log.debug("{} event triggered".format(event.name))
