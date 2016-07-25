from aiohttp import ClientSession
from copy import deepcopy
import logging
from tukio.task import register
from tukio.task.holder import TaskHolder

from nyuki.transform import Converter


log = logging.getLogger(__name__)


FACTORY_SCHEMAS = {
    'extract': {
        'type': 'object',
        'required': ['fieldname', 'regex_id'],
        'properties': {
            'fieldname': {'type': 'string', 'minLength': 1},
            'regex_id': {'type': 'string', 'minLength': 1},
            'pos': {'type': 'integer', 'minimum': 0},
            'endpos': {'type': 'integer', 'minimum': 0},
            'flags': {'type': 'integer'}
        }
    },
    'lookup': {
        'type': 'object',
        'required': ['fieldname', 'lookup_id'],
        'properties': {
            'fieldname': {'type': 'string', 'minLength': 1},
            'lookup_id': {'type': 'string', 'minLength': 1},
            'icase': {'type': 'boolean'}
        }
    },
    'set': {
        'type': 'object',
        'required': ['fieldname', 'value'],
        'properties': {
            'fieldname': {'type': 'string', 'minLength': 1},
            'value': {'type': 'string', 'minLength': 1},
        }
    },
    'sub': {
        'type': 'object',
        'required': ['fieldname', 'regex_id', 'repl'],
        'properties': {
            'fieldname': {'type': 'string', 'minLength': 1},
            'regex_id': {'type': 'string', 'minLength': 1},
            'repl': {'type': 'string', 'minLength': 1},
            'count': {'type': 'integer', 'minimum': 1},
            'flags': {'type': 'integer'}
        }
    },
    'unset': {
        'type': 'object',
        'required': ['fieldname'],
        'properties': {
            'fieldname': {'type': 'string', 'minLength': 1}
        }
    }
}


@register('factory', 'execute')
class FactoryTask(TaskHolder):

    SCHEMA = {
        'type': 'object',
        'required': ['rulers'],
        'properties': {
            'rulers': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'anyOf': [
                        {'$ref': '#/definitions/{}'.format(factory_type)}
                        for factory_type in FACTORY_SCHEMAS.keys()
                    ]
                }
            }
        },
        'definitions': {
            factory_type: {
                'type': 'object',
                'required': ['type', 'rules'],
                'properties': {
                    'type': {'type': 'string', 'enum': [factory_type]},
                    'rules': {
                        'type': 'array',
                        'items': FACTORY_SCHEMAS[factory_type]
                    }
                }
            } for factory_type in FACTORY_SCHEMAS.keys()
        }
    }
    BASE_API_URL = 'http://localhost:5558/v1/workflow'

    async def get_regexes(self, session, rules):
        """
        Query the nyuki to get the actual regexes from their IDs
        """
        for rule in rules:
            url = '{}/regexes/{}'.format(self.BASE_API_URL, rule['regex_id'])
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        'Could not find regex with id {}'.format(
                            rule['regex_id']
                        )
                    )
                data = await resp.json()
                rule['pattern'] = data['pattern']
                del rule['regex_id']

    async def get_lookups(self, session, rules):
        """
        Query the nyuki to get the actual lookup tables from their IDs
        """
        for rule in rules:
            url = '{}/lookups/{}'.format(self.BASE_API_URL, rule['lookup_id'])
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        'Could not find lookup table with id {}'.format(
                            rule['lookup_id']
                        )
                    )
                data = await resp.json()
                rule['table'] = data['table']
                del rule['lookup_id']

    async def get_factory_rules(self, config):
        """
        Iterate through the task's configuration to swap from their IDs to
        their database equivalent within the nyuki
        """
        async with ClientSession() as session:
            for ruler in config['rulers']:
                if ruler['type'] in ['extract', 'sub']:
                    await self.get_regexes(session, ruler['rules'])
                elif ruler['type'] == 'lookup':
                    await self.get_lookups(session, ruler['rules'])

    async def execute(self, event):
        data = event.data
        runtime_config = deepcopy(self.config)
        await self.get_factory_rules(runtime_config)
        log.debug('Full factory config: %s', runtime_config)
        converter = Converter.from_dict(runtime_config)
        converter.apply(data)
        return data
