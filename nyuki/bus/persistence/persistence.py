import asyncio
import logging

from nyuki.bus.persistence.mongo_backend import MongoBackend


log = logging.getLogger(__name__)


class PersistenceError(Exception):
    pass


class BusPersistence(object):

    """
    This module will enable local caching for bus events to replace the
    current asyncio cache which is out of our control. (cf internal NYUKI-59)
    """

    def __init__(self, backend, **kwargs):
        # TODO: mongo is the only one yet
        assert backend == 'mongo'
        self.backend = MongoBackend(**kwargs)

        # Ensure required methods are available, break if not
        assert hasattr(self.backend, 'init')
        assert hasattr(self.backend, 'store')
        assert hasattr(self.backend, 'retrieve')

    async def ping(self):
        """
        Connection check
        """
        return await self.backend.ping()

    async def init(self, *args, **kwargs):
        """
        Init
        """
        try:
            return await self.backend.init(*args, **kwargs)
        except Exception as exc:
            raise PersistenceError from exc

    async def store(self, *args, **kwargs):
        """
        Store a bus event as:
        {
            "topic": "muc",
            "message": "json dump"
        }
        """
        try:
            return await self.backend.store(*args, **kwargs)
        except Exception as exc:
            raise PersistenceError from exc

    async def retrieve(self, *args, **kwargs):
        """
        Must return the list of events stored since the given datetime:
        [{"topic": "muc", "message": "json dump"}]
        """
        try:
            return await self.backend.retrieve(*args, **kwargs)
        except Exception as exc:
            raise PersistenceError from exc
