import logging
from tukio.task import register
from tukio.task.holder import TaskHolder

from nyuki.transform import Converter


log = logging.getLogger(__name__)


FACTORY_SCHEMAS = {
    'extract': {
        'type': 'object',
        'required': ['fieldname', 'pattern'],
        'properties': {
            'fieldname': {'type': 'string', 'minLength': 1},
            'pattern': {'type': 'object', 'minLength': 1},
            'pos': {'type': 'integer', 'minimum': 0},
            'endpos': {'type': 'integer', 'minimum': 0},
            'flags': {'type': 'integer'}
        }
    },
    'lookup': {
        'type': 'object',
        'required': ['fieldname', 'table'],
        'properties': {
            'fieldname': {'type': 'string', 'minLength': 1},
            'table': {'type': 'object'},
            'icase': {'type': 'boolean'}
        }
    },
    'sub': {
        'type': 'object',
        'required': ['fieldname', 'pattern', 'repl'],
        'properties': {
            'fieldname': {'type': 'string', 'minLength': 1},
            'pattern': {'type': 'string', 'minLength': 1},
            'repl': {'type': 'string', 'minLength': 1},
            'count': {'type': 'integer', 'minimum': 1},
            'flags': {'type': 'integer'}
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
                        {'$ref': '#/definitions/extract'},
                        {'$ref': '#/definitions/lookup'},
                        {'$ref': '#/definitions/sub'},
                    ]
                }
            }
        },
        'definitions': {
            'extract': {
                'type': 'object',
                'required': ['type', 'rules'],
                'properties': {
                    'type': {'type': 'string', 'enum': ['extract']},
                    'rules': {
                        'type': 'array',
                        'items': FACTORY_SCHEMAS['extract']
                    }
                }
            },
            'lookup': {
                'type': 'object',
                'required': ['type', 'rules'],
                'properties': {
                    'type': {'type': 'string', 'enum': ['lookup']},
                    'rules': {
                        'type': 'array',
                        'items': FACTORY_SCHEMAS['lookup']
                    }
                }
            },
            'sub': {
                'type': 'object',
                'required': ['type', 'rules'],
                'properties': {
                    'type': {'type': 'string', 'enum': ['sub']},
                    'rules': {
                        'type': 'array',
                        'items': FACTORY_SCHEMAS['sub']
                    }
                }
            }
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
