import logging

from nyuki.bus.persistence.mongo_backend import MongoBackend


log = logging.getLogger(__name__)


class BusPersistence(object):

    def __init__(self, backend, **kwargs):
        # TODO: mongo is the only one yet
        assert backend == 'mongo'
        self.backend = MongoBackend(**kwargs)

        # Ensure required methods are available, break if not
        assert hasattr(self.backend, 'init')
        assert hasattr(self.backend, 'store')
        assert hasattr(self.backend, 'retrieve')

    @property
    def init(self):
        """
        Init
        """
        return self.backend.init

    @property
    def store(self):
        """
        Store a bus event as:
        {
            "topic": "muc",
            "message": "json dump"
        }
        """
        return self.backend.store

    @property
    def retrieve(self):
        """
        Must return the list of events stored since the given datetime:
        [{"topic": "muc", "message": "json dump"}]
        """
        return self.backend.retrieve
