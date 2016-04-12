import logging

from nyuki.bus.persistence.mongo_backend import MongoBackend


log = logging.getLogger(__name__)


class BusPersistence(object):

    def __init__(self, backend, name):
        # TODO: mongo is the only one yet
        assert backend == 'mongo'
        self.backend = MongoBackend(name)

    async def init(self, *args, **kwargs):
        log.info('Backend set to %s', self.backend)
        return await self.backend.init(*args, **kwargs)

    async def store(self, topic, message):
        log.debug('Storing bus event')
        return await self.backend.store(topic, message)

    async def retrieve(self, since=None):
        log.debug('Retrieving events from storage')
        return await self.backend.retrieve(since)
