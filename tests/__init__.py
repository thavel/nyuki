import asyncio
from functools import wraps
from unittest import TestCase
from unittest.mock import MagicMock


class AsyncMock(MagicMock):

    """
    Enable the python3.5 'await' call to a magicmock
    """

    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


def make_future(res=None):
    f = asyncio.Future()
    f.set_result(res)
    return f


def future_func(func):
    """
    Decorator that takes an plain old python function/method and wraps the
    result of its execution inside an asyncio.Future.
    """
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        return make_future(func(*args, **kwargs))
    return func_wrapper
