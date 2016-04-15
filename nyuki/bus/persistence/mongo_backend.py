from datetime import datetime
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import AutoReconnect

from nyuki.bus.persistence import EventStatus


log = logging.getLogger(__name__)


class MongoNotConnectedError(Exception):
    pass


class MongoBackend(object):

    def __init__(self, name, host, ttl=60):
        self.name = name
        self.client = None
        self.host = host
        self.ttl = ttl
        self._collection = None
        # Ensure TTL is set
        self._indexed = False

    def __str__(self):
        return "<MongoBackend with host '{}'>".format(self.host)

    async def ping(self):
        try:
            await self.client.admin.command('ping')
        except AutoReconnect:
            return False
        else:
            return True

    async def init(self):
        # Get collection for this nyuki
        self.client = AsyncIOMotorClient(self.host)
        db = self.client['bus_persistence']
        self._collection = db[self.name]
        await self._index_ttl()

    async def _index_ttl(self):
        # Set a TTL to the documents in this collection
        await self._collection.create_index(
            'created_at', expireAfterSeconds=self.ttl*60
        )
        self._indexed = True

    async def store(self, event):
        if not await self.ping():
            raise MongoNotConnectedError

        if not self._indexed:
            await self._index_ttl()

        await self._collection.insert({
            **event,
            'created_at': datetime.utcnow(),
        })

    async def retrieve(self, since=None, status=None):
        if not await self.ping():
            raise MongoNotConnectedError

        query = {}

        if since:
            query['created_at'] = {'$gte': since}

        if status and isinstance(status, EventStatus):
            if isinstance(status, list):
                query['status'] = {'$in': [es.value for es in status]}
            else:
                query['status'] = status.value

        cursor = self._collection.find(query)
        cursor.sort('created_at')

        return await cursor.to_list(None)
