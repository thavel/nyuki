def generate_schema(properties={}, definitions={}):
    """
    Append custom object properties to the base selector schema.
    """
    return {
        'type': 'object',
        'required': ['selectors'],
        'properties': {
            **properties,
            'selectors': {
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
            'values': {
                'type': 'array',
                'items': {
                    'type': 'string',
                    'minLength': 1,
                    'uniqueItems': True
                }
            },
            'selector': {
                'type': 'object',
                'required': ['type', 'values'],
                'properties': {
                    'type': {'type': 'string', 'enum': ['selector']},
                    'values': {'$ref': '#/definitions/values'}
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
                'required': ['type', 'condition', 'values'],
                'properties': {
                    'type': {'type': 'string', 'enum': ['if', 'elif']},
                    'condition': {'type': 'string', 'minLength': 1},
                    'values': {'$ref': '#/definitions/values'}
                }
            },
            'condition-else': {
                'type': 'object',
                'required': ['type', 'values'],
                'properties': {
                    'type': {'type': 'string', 'enum': ['else']},
                    'values': {'$ref': '#/definitions/values'}
                }
            }
        }
    }
