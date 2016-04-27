import logging
import asyncio
from inspect import getmembers, isclass, isfunction

from nyuki.api import Method
from nyuki.capabilities import Capability


log = logging.getLogger(__name__)


class CapabilityHandler(type):

    ALLOWED_METHODS = Method.list()

    def __call__(cls, *args, **kwargs):
        """
        Register decorated resources and methods to be routed by the web app.
        """
        nyuki = super().__call__(*args, **kwargs)
        for resrc, desc in cls._filter_resource(nyuki):
            version = desc.version
            endpoint = desc.endpoint
            content_type = desc.content_type
            for method, handler in cls._filter_capability(desc):
                name = '{}_{}'.format(method, resrc)
                wrapper = cls._build_wrapper(nyuki, handler)
                wrapper.CONTENT_TYPE = content_type
                nyuki.api.register(Capability(
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
        return asyncio.coroutine(
            lambda req, **kwargs: func(obj, req, **kwargs)
        )

    @classmethod
    def _filter_capability(mcs, resrc):
        """
        Find methods decorated with `capability`.
        """
        for name, handler in getmembers(resrc, isfunction):
            method = name.upper()
            if method not in mcs.ALLOWED_METHODS:
                raise ValueError("{} is not a valid HTTP method".format(method))
            yield method, handler

    @staticmethod
    def _filter_resource(obj):
        """
        Find nested classes decorated with `endpoint`.
        """
        for name, cls in getmembers(obj, isclass):
            if hasattr(cls, 'endpoint'):
                yield name, cls
