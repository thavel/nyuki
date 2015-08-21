import asyncio
from functools import wraps
from unittest import TestCase


def fake_future(func):
    """
    Decorator that takes an plain old python function/method and wraps the
    result of its execution inside an asyncio.Future.
    """
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        f = asyncio.Future()
        f.set_result(func(*args, **kwargs))
        return f
    return func_wrapper


class AsyncTestCase(TestCase):

    def setUp(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

    def tearDown(self):
        self._loop.close()
