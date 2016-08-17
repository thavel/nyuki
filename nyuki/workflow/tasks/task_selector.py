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

    def apply(self, data, workflow):
        for cond in self._conditions:
            # If type 'else', set given next tasks and leave
            if cond['type'] == 'else':
                workflow.set_next_tasks(cond['tasks'])
                return
            # Else find the condition and evaluate it
            if self.evaluate(cond['condition'], data):
                workflow.set_next_tasks(cond['tasks'])
                return


@register('task_selector', 'execute')
class TaskSelector(TaskHolder):

    SCHEMA = {
        'type': 'object',
        'required': ['conditions'],
        'properties': {
            'conditions': {
                'type': 'array',
                'items': {
                    'oneOf': [
                        {'$ref': '#/definitions/condition-if'},
                        {'$ref': '#/definitions/condition-else'}
                    ]
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
        block = TaskConditionBlock(self.config['conditions'])
        block.apply(data, workflow)
        return data
