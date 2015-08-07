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

        self._loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        assert isinstance(self._loop, BaseEventLoop)

        self._setup = setup
        self._teardown = teardown

        self._timeouts = dict()

    @property
    def loop(self):
        return self._loop

    def is_running(self):
        """
        An running event loop is so when the thread is still active and the
        asyncio loop within is running.
        """
        return self._thread.is_alive() and self._loop.is_running()

    def start(self, block=False):
        """
        Run the asyncio loop in its own thread, or in the current thread if the
        parameter `block` is true.
        """
        def run():
            log.debug("The event loop is starting")
            try:
                self._setup()
                self._loop.run_forever()
            finally:
                self._teardown()
            self._loop.close()
            log.debug("The event loop has been stopped")

        self._blocking = block
        if block:
            self._thread = threading.current_thread()
            run()
        else:
            self._thread = threading.Thread(target=run)

    def stop(self, timeout=None):
        """
        Stop the event loop and wait until its thread stop (if it is a
        non-blocking event loop). The `timeout` raises an exception if the
        thread didn't end within the specified amount of time (in secs).
        """
        if not self.is_running():
            return

        self._loop.call_soon_threadsafe(self._loop.stop)
        # If the loop is non-blocking, we also stop its thread.
        if not self._blocking:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                raise TimeoutError("Event loop failed to stop "
                                   "in {} seconds".format(timeout))

    def schedule(self, delay, callback, *args):
        """
        Useful method to schedule a callback using the event loop.
        """
        self._loop.call_later(delay, callback *args)

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
        future = self._loop.call_at(deadline, wrapper, *args)
        self._timeouts[key] = future

    def cancel_timeout(self, key):
        """
        Cancel a timeout that has been previously added to the event loop.
        """
        if key not in self._timeouts:
            raise ValueError('This timeout key does not exist')
        coro = self._timeouts[key]
        coro.cancel()
        del self._timeouts[key]
