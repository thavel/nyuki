import logging

from nyuki.bus.persistence.backend import PersistenceBackend
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
        # TODO: mongo is the only one yet, we should parse available modules
        #       named `*_backend.py` and select after the given backend.
        if backend != 'mongo':
            raise ValueError("'mongo' is the only available backend")

        self.backend = MongoBackend(**kwargs)

        if not isinstance(self.backend, PersistenceBackend):
            raise PersistenceError('Wrong backend selected: {}'.format(backend))

    async def init(self):
        """
        Init
        """
        try:
            return await self.backend.init()
        except Exception as exc:
            raise PersistenceError from exc

    async def ping(self):
        """
        Connection check
        """
        return await self.backend.ping()

    async def store(self, event):
        """
        Store a bus event as:
        {
            "id": "uuid4",
            "status": "EventStatus.value"
            "topic": "muc",
            "message": "json dump"
        }
        """
        try:
            return await self.backend.store(event)
        except Exception as exc:
            raise PersistenceError from exc

    async def update(self, uid, status):
        """
        Store a bus event as:
        {
            "id": "uuid4",
            "status": "EventStatus.value"
            "topic": "muc",
            "message": "json dump"
        }
        """
        log.info("Updating stored event '%s' with status '%s'", uid, status)
        try:
            return await self.backend.update(uid, status)
        except Exception as exc:
            raise PersistenceError from exc

    async def retrieve(self, since=None, status=None):
        """
        Must return the list of events stored since the given datetime
        """
        try:
            return await self.backend.retrieve(since=since, status=status)
        except Exception as exc:
            raise PersistenceError from exc
