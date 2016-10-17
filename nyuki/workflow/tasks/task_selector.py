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
        self._selected = None

    def condition_validated(self, rules, data):
        """
        Set next workflow tasks upon validating a condition.
        """
        if rules:
            self._workflow.set_next_tasks(rules[0]['tasks'])
            self._selected = rules[0]['tasks']

    def apply(self, data):
        super().apply(data)
        return self._selected


@register('task_selector', 'execute')
class TaskSelector(TaskHolder):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._selected = None

    SCHEMA = generate_schema(tasks={
        'type': 'object',
        'required': ['type', 'tasks'],
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
        self._selected = None
        for block in self.config['rules']:
            if block['type'] == 'task-selector':
                workflow.set_next_tasks(block['tasks'])
                self._selected = block['tasks']
            elif block['type'] == 'condition-block':
                selected = TaskConditionBlock(block['conditions'], workflow).apply(data)
                if selected is not None:
                    self._selected = selected

        log.debug('Tasks selected: %s', self._selected)
        return data

    def report(self):
        return {'tasks': self._selected}
