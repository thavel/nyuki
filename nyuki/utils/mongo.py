import logging

from motor.motor_asyncio import AsyncIOMotorClient


log = logging.getLogger(__name__)
SITE_HEADER = 'X-Surycat-Site'


class _DatabaseContext:

    def __init__(self, client, storage, init=False):
        self._client = client
        self._storage = storage
        self._init = init

    async def __aenter__(self):
        # Raise AutoReconnect if command has failed
        await self._client.admin.command('ping')
        if self._init is True:
            await self._storage.init()
        return self._storage

    async def __aexit__(self, *args):
        pass


class MongoManager:

    DATABASE_PREFIX = 'site-'
    DEFAULT_DATABASE = 'default'
    DEFAULT_COL_PREFIX = 'default'

    def __init__(self, cls, host, prefix=None, **kwargs):
        self._client = AsyncIOMotorClient(host, **kwargs)
        self._storage_cls = cls
        self._databases = {}
        # Collection's prefix
        self._prefix = prefix or self.DEFAULT_COL_PREFIX

    def _db_name(self, name):
        return '{}{}'.format(
            self.DATABASE_PREFIX, name or self.DEFAULT_DATABASE
        )

    async def drop_database(self, name):
        """
        Drop the database with given name.
        """
        name = self._db_name(name)
        await self._client.drop_database(name)

    async def list_databases(self):
        """
        List all organization databases.
        """
        names = await self._client.database_names()
        return [
            name.replace(self.DATABASE_PREFIX, '')
            for name in names if name.startswith(self.DATABASE_PREFIX)
        ]

    async def database(self, name):
        """
        Return a storage object for the requested database.
        """
        # Raise AutoReconnect if command has failed
        await self._client.admin.command('ping')
        name = self._db_name(name)
        log.debug('Using database: %s', name)
        if name not in self._databases:
            log.info("Setting up storage on database '%s'", name)
            db = self._storage_cls(self._client[name], self._prefix)
            await db.init()
            self._databases[name] = db
        return self._databases[name]

    def db_context(self, name):
        """
        Return an async context manager yielding a storage object for
        the request database.
        """
        init = False
        name = self._db_name(name)
        log.debug('Using database: %s', name)
        if name not in self._databases:
            log.info("Setting up storage on database '%s'", name)
            self._databases[name] = self._storage_cls(self._client[name], self._prefix)
            init = True
        return _DatabaseContext(self._client, self._databases[name], init)
