import logging
import threading
import asyncio
from asyncio.base_events import BaseEventLoop


log = logging.getLogger(__name__)


class EventLoop(object):
    """
    A generic thread-safe asyncio event loop wrapper.
    """

    def __init__(self, loop=None):
        """
        Init the event loop using an existing (non-running) loop or a new one,
        and define optional callbacks that would be executed at the beginning
        and the end of the loop lifecycle.
        """
        self._thread = None
        self._blocking = False
        self._timeouts = dict()

        self._loop = self._init_loop(loop)

    def __str__(self):
        alive = 'alive' if self.is_running() else 'down'
        if self._thread:
            blocking = 'blocking' if self._blocking else 'not blocking'
        else:
            blocking = 'wrapped'
        timeouts = '{} timeout(s)'.format(len(self._timeouts))
        address = hex(id(self))
        return '<{}: {}, {}, {} at {}>'.format(
            self.__class__.__name__, alive, blocking, timeouts, address
        )

    def _init_loop(self, loop):
        """
        Handle wrapper init if the an existing loop is given.
        """
        if not loop:
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
            return _loop

        assert isinstance(loop, BaseEventLoop)
        if loop.is_running():
            # Asyncio is supposed to be single-threaded but we can't assume we
            # are in the very thread use by asyncio (we're maybe in a callback
            # fired with `call_soon_threadsafe` on a differend thread.
            # So, let's say it's a blocking loop.
            self._blocking = True
            self._thread = None
        return loop

    @property
    def loop(self):
        return self._loop

    def is_running(self):
        """
        An running event loop is so when the thread is still active and the
        asyncio loop within is running.
        """
        if not self._thread:
            return self._loop.is_running()
        return self._thread.is_alive() and self._loop.is_running()

    def start(self, block=False):
        """
        Run the asyncio loop in its own thread, or in the current thread if the
        parameter `block` is true.
        """
        def run():
            log.debug("The event loop is starting")
            self._loop.run_forever()
            self._loop.close()
            log.debug("The event loop has been stopped")

        if self.is_running():
            raise RuntimeError("This event loop has already been started")

        self._blocking = block
        if block:
            self._thread = threading.current_thread()
            run()
        else:
            self._thread = threading.Thread(target=run)
            self._thread.start()

    def stop(self, timeout=None):
        """
        Stop the event loop and wait until its thread stop (if it is a
        non-blocking event loop). The `timeout` raises an exception if the
        thread didn't end within the specified amount of time (in secs).
        """
        if not self.is_running():
            raise RuntimeError("This event loop hasn't been started yet")

        self._loop.call_soon_threadsafe(self._loop.stop)
        # If the loop is non-blocking, we also stop its thread.
        if not self._blocking and self._thread:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                raise TimeoutError("Event loop failed to stop "
                                   "in {} seconds".format(timeout))

    def async(self, callback, *args):
        """
        Perform a simple asynchronous call using the event loop.
        """
        self._loop.call_soon(callback, *args)

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
            raise ValueError("This timeout key does not exist")
        coro = self._timeouts[key]
        coro.cancel()
        del self._timeouts[key]
