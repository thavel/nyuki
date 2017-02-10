import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import AutoReconnect, OperationFailure


log = logging.getLogger(__name__)


class MongoNotConnectedError(Exception):
    pass


class ConfigMongoBackend(object):

    def __init__(self, host='localhost', **kwargs):
        self.client = None
        self.host = host
        self._options = kwargs

    def __str__(self):
        return "<ConfigMongoBackend with host '{}'>".format(self.host)

    async def ping(self):
        try:
            await self.client.admin.command('ping')
        except AutoReconnect:
            return False
        else:
            return True

    async def init(self):
        # Get collection for this nyuki
        self.client = AsyncIOMotorClient(self.host, **self._options)

    def get_orga_config(orga_id):
        """
        TODO: improve this to keep recent client dbs in memory but clean old ones.
        we shouldn't have to maintain a connection with all clients db if these are inactive
        """
        client_db = self.client[orga_id]
        client_config = client_db['config']  #TODO make that configurable ?
        return client_config

    async def set(self, orga, key, data):
        if not await self.ping():
            raise MongoNotConnectedError
        collection = self.get_orga_config(orga)

        await db.test_collection.find().count()
        await collection.update_one({}, {'$set': {'key': data}})
        await self.get_orga_config(orga).insert(event)

    async def get(self, orga, key=None):
        """
        TODO: add optional key to filter result
        """
        if not await self.ping():
            raise MongoNotConnectedError
        collection = self.get_orga_config(orga)

        cursor = collection.find_one({})

        return await cursor if key is None else cursor.get(key)
