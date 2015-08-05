import asyncio
import logging
import threading
import functools


log = logging.getLogger(__name__)


class TimeoutError(Exception):
    pass


def _async(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if self._thread is not None \
                and self._thread.ident != threading.get_ident():
            wrapped_func = functools.partial(func, self, *args, **kwargs)
            self._loop.call_soon_threadsafe(wrapped_func)
        else:
            func(self, *args, **kwargs)
    return wrapper


class Looping(object):
    """
    A generic thread-safe asyncio loop runner.
    """
    def __init__(self, loop=None):
        self._loop = loop
        self._thread = None
        # store setup/teardown handlers. Each handler receives a loop as
        # argument.
        self.setup = self._setup
        self.teardown = self._teardown

    @property
    def loop(self):
        return self._loop

    @property
    def running(self):
        if self._thread:
            return self._thread.is_alive()
        else:
            return False

    def _run(self):
        """
        Create if required an new event loop and run it
        """
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        log.debug("start to run event loop")
        try:
            self.setup(self._loop)
            self._loop.run_forever()
        finally:
            try:
                self.teardown(self._loop)
            finally:
                # cleanup the loop at all cases!
                self._loop.close()
                log.debug("event loop stopped")

    def start(self, name=None, block=False):
        """
        Run an asyncio event loop in its own thread. If `block`is True, just
        try to run the event loop in the current thread.
        """
        name_kwd = {}
        if name is not None:
            name_kwd = {'name': name}
        if block:
            self._thread = threading.current_thread()
            self._run()
        else:
            self._thread = threading.Thread(target=self._run, **name_kwd)
            self._thread.start()

    @_async
    def _stop(self):
        """
        Thread-safe wrapper to stop the event loop.
        """
        if self._loop:
            self._loop.stop()

    def stop(self, timeout=None):
        """
        Stop the event loop and wait until its thread stopped. If `timeout` is
        not None, it must be an integer or a float that gives the maximum amount
        of time (in seconds) to wait before raising a `TimeoutError` exception.
        """
        self._stop()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                raise TimeoutError("event loop did not stop in {} seconds".format(timeout))

    def _setup(self, loop=None):
        """
        Code your own setup process that will be executed just before the call
        to `loop.run_forever()`. This code will be executed within the thread
        running the event loop.
        """
        pass

    def _teardown(self, loop=None):
        """
        Code your own teardown process that will be executed just after
        `loop.run_forever` has returned or raised an exception. This code will
        be executed within the thread running the event loop.
        Note that if `loop.run_forever` raises an exception, it will be
        propagated to the caller of the `start()` method.
        Must be overridden.
        """
        pass
