import logging
import threading
import asyncio
from asyncio.base_events import BaseEventLoop


log = logging.getLogger(__name__)


class EventLoop(object):
    """
    A generic thread-safe asyncio event loop wrapper.
    """

    def __init__(self, loop=None, setup=None, teardown=None):
        """
        Init the event loop using an existing (non-running) loop or a new one,
        and define optional callbacks that would be executed at the beginning
        and the end of the loop lifecycle.
        """
        self._thread = None
        self._blocking = False

        self._loop = loop or asyncio.get_event_loop()
        assert isinstance(self._loop, BaseEventLoop)
        if loop:
            asyncio.set_event_loop(loop)

        self._timeouts = dict()

    def __str__(self):
        alive = 'alive' if self.is_running() else 'down'
        blocking = 'blocking' if self._blocking else 'not blocking'
        timeouts = '{} timeout(s)'.format(len(self._timeouts))
        address = hex(id(self))
        return '<{}: {}, {}, {} at {}>'.format(
            self.__class__.__name__, alive, blocking, timeouts, address
        )

    @property
    def loop(self):
        return self._loop

    def is_running(self):
        """
        An running event loop is so when the thread is still active and the
        asyncio loop within is running.
        """
        return self._loop.is_running()

    def schedule(self, delay, callback, *args):
        """
        Useful method to schedule a callback using the event loop.
        """
        self._loop.call_later(delay, callback, *args)

    def add_timeout(self, key, deadline, callback, *args):
        """
        Useful method to handle timeout using the event loop.
        """
        # Wrapper to remove the timeout from the dict when it is called
        def wrapper(*args):
            callback(*args)
            del self._timeouts[key]

        if key in self._timeouts:
            raise ValueError("This timeout key already exists")
        deadline += self._loop.time()
        handle = self._loop.call_at(deadline, wrapper, *args)
        self._timeouts[key] = handle

    def cancel_timeout(self, key):
        """
        Cancel a timeout that has been previously added to the event loop.
        """
        if key not in self._timeouts:
            raise ValueError('This timeout key does not exist')
        coro = self._timeouts[key]
        coro.cancel()
        del self._timeouts[key]
