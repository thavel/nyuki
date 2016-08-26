import logging
from tukio import Workflow
from tukio.task import register
from tukio.task.holder import TaskHolder

from nyuki.utils.evaluate import ConditionBlock
from nyuki.workflow.tasks.utils import generate_schema


log = logging.getLogger(__name__)


class TaskConditionBlock(ConditionBlock):

    """
    Overrides work on ConditionBlock from the factory task to
    set next workflow tasks.
    """

    def __init__(self, conditions, workflow):
        super().__init__(conditions)
        self._workflow = workflow

    def condition_validated(self, rules, data):
        """
        Set next workflow tasks upon validating a condition.
        """
        if rules:
            self._workflow.set_next_tasks(rules[0]['tasks'])


@register('task_selector', 'execute')
class TaskSelector(TaskHolder):

    SCHEMA = generate_schema(tasks={
        'type': 'object',
        'properties': {
            'type': {'type': 'string', 'enum': ['task-selector']},
            'tasks': {
                'type': 'array',
                'items': {
                    'type': 'string',
                    'minLength': 1,
                    'uniqueItems': True
                }
            }
        }
    })

    async def execute(self, event):
        data = event.data
        workflow = Workflow.current_workflow()
        for block in self.config['rules']:
            if block['type'] == 'task-selector':
                workflow.set_next_tasks(block['tasks'])
            elif block['type'] == 'condition-block':
                TaskConditionBlock(block['conditions'], workflow).apply(data)
        return data
