def generate_schema(properties={}, definitions={}):
    """
    Append custom object properties to the base selector schema.
    """
    return {
        'type': 'object',
        'required': ['rules'],
        'properties': {
            **properties,
            'rules': {
                'type': 'array',
                'items': {
                    'oneOf': [
                        {'$ref': '#/definitions/condition-block'},
                        {'$ref': '#/definitions/selector'}
                    ]
                }
            }
        },
        'definitions': {
            **definitions,
            'rules': {
                'type': 'array',
                'items': {
                    'type': 'string',
                    'minLength': 1,
                    'uniqueItems': True
                }
            },
            'selector': {
                'type': 'object',
                'required': ['type', 'rules'],
                'properties': {
                    'type': {'type': 'string', 'enum': ['selector']},
                    'rules': {'$ref': '#/definitions/rules'}
                }
            },
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
            }
        }
    }
