from aiohttp import ClientSession
from copy import deepcopy
import logging
from tukio.task import register
from tukio.task.holder import TaskHolder

from nyuki.utils import Converter
from nyuki.workflow.tasks.utils import runtime


log = logging.getLogger(__name__)


FACTORY_SCHEMAS = {
    'condition-block': {
        'type': 'object',
        'required': ['type', 'conditions'],
        'properties': {
            'type': {'type': 'string', 'enum': ['condition-block']},
            'conditions': {
                'type': 'array',
                'items': {
                    'oneOf': [
                        {'$ref': '#/definitions/condition-if'},
                        {'$ref': '#/definitions/condition-else'}
                    ]
                }
            }
        }
    },
    'extract': {
        'type': 'object',
        'required': ['type', 'fieldname', 'regex_id'],
        'properties': {
            'type': {'type': 'string', 'enum': ['extract']},
            'fieldname': {'type': 'string', 'minLength': 1},
            'regex_id': {'type': 'string', 'minLength': 1},
            'pos': {'type': 'integer', 'minimum': 0},
            'endpos': {'type': 'integer', 'minimum': 0},
            'flags': {'type': 'integer'}
        }
    },
    'lookup': {
        'type': 'object',
        'required': ['type', 'fieldname', 'lookup_id'],
        'properties': {
            'type': {'type': 'string', 'enum': ['lookup']},
            'fieldname': {'type': 'string', 'minLength': 1},
            'lookup_id': {'type': 'string', 'minLength': 1},
            'icase': {'type': 'boolean'}
        }
    },
    'set': {
        'type': 'object',
        'required': ['type', 'fieldname', 'value'],
        'properties': {
            'type': {'type': 'string', 'enum': ['set']},
            'fieldname': {'type': 'string', 'minLength': 1},
            'value': {'type': 'string', 'minLength': 1},
        }
    },
    'sub': {
        'type': 'object',
        'required': ['type', 'fieldname', 'regex_id', 'repl'],
        'properties': {
            'type': {'type': 'string', 'enum': ['sub']},
            'fieldname': {'type': 'string', 'minLength': 1},
            'regex_id': {'type': 'string', 'minLength': 1},
            'repl': {'type': 'string', 'minLength': 1},
            'count': {'type': 'integer', 'minimum': 1},
            'flags': {'type': 'integer'}
        }
    },
    'unset': {
        'type': 'object',
        'required': ['type', 'fieldname'],
        'properties': {
            'type': {'type': 'string', 'enum': ['unset']},
            'fieldname': {'type': 'string', 'minLength': 1}
        }
    }
}


@register('factory', 'execute')
class FactoryTask(TaskHolder):

    SCHEMA = {
        'type': 'object',
        'required': ['rules'],
        'properties': {
            'rules': {'$ref': '#/definitions/rules'}
        },
        'definitions': {
            'rules': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'anyOf': [
                        {'$ref': '#/definitions/{}'.format(factory_type)}
                        for factory_type in FACTORY_SCHEMAS.keys()
                    ]
                }
            },
            'condition-if': {
                'type': 'object',
                'required': ['type', 'condition', 'rules'],
                'properties': {
                    'type': {'type': 'string', 'enum': ['if', 'elif']},
                    'condition': {'type': 'string', 'minLength': 1},
                    'rules': {'$ref': '#/definitions/rules'}
                }
            },
            'condition-else': {
                'type': 'object',
                'required': ['type', 'rules'],
                'properties': {
                    'type': {'type': 'string', 'enum': ['else']},
                    'rules': {'$ref': '#/definitions/rules'}
                }
            },
            **{factory_type: FACTORY_SCHEMAS[factory_type]
               for factory_type in FACTORY_SCHEMAS.keys()},
        }
    }

    def __init__(self, config):
        super().__init__(config)
        self.api_url = 'http://localhost:{}/v1/workflow'.format(
            runtime.config['api']['port']
        )

    async def get_regex(self, session, rule):
        """
        Query the nyuki to get the actual regexes from their IDs
        """
        url = '{}/regexes/{}'.format(self.api_url, rule['regex_id'])
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

    async def get_lookup(self, session, rule):
        """
        Query the nyuki to get the actual lookup tables from their IDs
        """
        url = '{}/lookups/{}'.format(self.api_url, rule['lookup_id'])
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
            for rule in config['rules']:
                if rule['type'] in ['extract', 'sub']:
                    await self.get_regex(session, rule)
                elif rule['type'] == 'lookup':
                    await self.get_lookup(session, rule)

    async def execute(self, event):
        data = event.data
        runtime_config = deepcopy(self.config)
        await self.get_factory_rules(runtime_config)
        log.debug('Full factory config: %s', runtime_config)
        converter = Converter.from_dict(runtime_config)
        log.debug('Before convertion: %s', data)
        converter.apply(data)
        log.debug('After convertion: %s', data)
        return data
