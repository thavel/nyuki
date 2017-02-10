import asyncio
import json
import logging
from jsonschema import validate, ValidationError

from nyuki.services import Service

from mongo_backend import ConfigMongoBackend

log = logging.getLogger(__name__)

class OrganizationConfig(object):
    """
    Enables to set or fetch an organization configuration using:
    config.get() -> returns a dictionary of the configuration
    config.set(config) -> set the new configuration
    Later: will need to be able to do atomic updates of the configuration
    """

    def __init__(self, backend, loop=None, **kwargs):
        """
        TODO: mongo is the only one yet, we should parse available modules
              named `*_backend.py` and select after the given backend.
        """
        self._loop = loop or asyncio.get_event_loop()
        self.backend = config.get('backend')

        if not backend:
            log.info('No persistence backend selected, in-memory only')
            return

        if backend != 'mongo':
            raise ValueError("'mongo' is the only available backend")

        self.backend = ConfigMongoBackend(**kwargs)

    def get(self, orga, key=None):
        return self.backend.get(orga)

    def set(self, orga, key, data):
        return self.backend.set(orga, key, data)
