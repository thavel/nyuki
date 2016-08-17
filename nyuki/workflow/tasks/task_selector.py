import logging
from tukio import Workflow
from tukio.task import register
from tukio.task.holder import TaskHolder

from nyuki.utils.evaluate import ConditionBlock


log = logging.getLogger(__name__)


class TaskConditionBlock(ConditionBlock):

    """
    Overrides work on ConditionBlock from the factory task to
    set next workflow tasks.
    """

    def __init__(self, conditions, workflow):
        super().__init__(conditions)
        self._workflow = workflow

    def condition_validated(self, condition, data):
        """
        Set next workflow tasks upon validating a condition.
        """
        self._workflow.set_next_tasks(condition['tasks'])


@register('task_selector', 'execute')
class TaskSelector(TaskHolder):

    SCHEMA = {
        'type': 'object',
        'required': ['rules'],
        'properties': {
            'rules': {
                'type': 'array',
                'items': {
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
        'definitions': {
            'condition-if': {
                'type': 'object',
                'required': ['type', 'condition', 'tasks'],
                'properties': {
                    'type': {'type': 'string', 'enum': ['if', 'elif']},
                    'condition': {'type': 'string', 'minLength': 1},
                    'tasks': {
                        'type': 'array',
                        'items': {'type': 'string', 'minLength': 1}
                    }
                }
            },
            'condition-else': {
                'type': 'object',
                'required': ['type', 'tasks'],
                'properties': {
                    'type': {'type': 'string', 'enum': ['else']},
                    'tasks': {
                        'type': 'array',
                        'items': {'type': 'string', 'minLength': 1}
                    }
                }
            }
        }
    }

    async def execute(self, event):
        data = event.data
        workflow = Workflow.current_workflow()
        for rule in self.config['rules']:
            TaskConditionBlock(rule['conditions'], workflow).apply(data)
        return data
