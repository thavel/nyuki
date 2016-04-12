from datetime import datetime
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import AutoReconnect


log = logging.getLogger(__name__)


class MongoBackend(object):

    def __init__(self, name, host, ttl=60):
        self.name = name
        self.host = host
        self.ttl = ttl
        self._collection = None

    def __str__(self):
        return "<MongoBackend with host '{}'>".format(self.host)

    async def init(self):
        # Get collection for this nyuki
        client = AsyncIOMotorClient(self.host)
        db = client['bus_persistence']
        self._collection = db[self.name]

        # Set a TTL to the documents in this collection
        try:
            await self._collection.create_index(
                'created_at', expireAfterSeconds=self.ttl*60
            )
        except AutoReconnect:
            # TODO: NYUKI-57, reporting infinite loop
            log.error("Could not reach mongo at address '%s'", self.host)

    async def store(self, topic, message):
        try:
            await self._collection.insert({
                'created_at': datetime.utcnow(),
                'topic': str(topic),
                'message': message
            })
        except AutoReconnect:
            # TODO: NYUKI-57, reporting infinite loop
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
            # TODO: NYUKI-57, reporting infinite loop
            log.error("Could not reach mongo at address '%s'", self.host)
