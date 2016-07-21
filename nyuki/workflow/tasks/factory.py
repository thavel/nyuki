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
            # 'pattern': {'type': 'object', 'minLength': 1},
            # 'pos': {'type': 'integer', 'minimum': 0},
            # 'endpos': {'type': 'integer', 'minimum': 0},
            # 'flags': {'type': 'integer'}
        }
    },
    'lookup': {
        'type': 'object',
        'required': ['fieldname', 'lookup_id'],
        'properties': {
            'fieldname': {'type': 'string', 'minLength': 1},
            'lookup_id': {'type': 'string', 'minLength': 1},
            # 'table': {'type': 'object'},
            # 'icase': {'type': 'boolean'}
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
            # 'pattern': {'type': 'object', 'minLength': 1},
            # 'count': {'type': 'integer', 'minimum': 1},
            # 'flags': {'type': 'integer'}
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

    async def execute(self, event):
        """
        Factory task that apply regexes and lookups.
        """
        data = event.data
        converter = Converter.from_dict(self.config)
        converter.apply(data)
        return data
