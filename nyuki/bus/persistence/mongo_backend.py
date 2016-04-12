from datetime import datetime
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import AutoReconnect


log = logging.getLogger(__name__)


class MongoBackend(object):

    def __init__(self, name):
        self.name = name
        self.host = None
        self._collection = None

    async def init(self, host, ttl=60):
        self.host = host
        # Get collection for this nyuki
        client = AsyncIOMotorClient(host)
        db = client['bus_persistence']
        self._collection = db[self.name]

        # Set a TTL to the documents in this collection
        try:
            await self._collection.create_index(
                'created_at', expireAfterSeconds=ttl*60
            )
        except AutoReconnect:
            log.error("Could not reach mongo at address '%s'", self.host)

    async def store(self, topic, message):
        try:
            await self._collection.insert({
                'created_at': datetime.utcnow(),
                'topic': str(topic),
                'message': message
            })
        except AutoReconnect:
            log.error("Could not reach mongo at address '%s'", self.host)

    async def retrieve(self, since=None):
        if since:
            cursor = self._collection.find({'created_at': {'$gte': since}})
        else:
            cursor = self._collection.find()

        cursor.sort('created_at')

        try:
            return await cursor.to_list(None)
        except AutoReconnect:
            log.error("Could not reach mongo at address '%s'", self.host)
