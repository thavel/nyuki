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

    def condition_validated(self, condition, data):
        """
        Set next workflow tasks upon validating a condition.
        """
        self._workflow.set_next_tasks(condition['values'])


@register('task_selector', 'execute')
class TaskSelector(TaskHolder):

    SCHEMA = generate_schema()

    async def execute(self, event):
        data = event.data
        workflow = Workflow.current_workflow()
        for block in self.config['rules']:
            if block['type'] == 'selector':
                workflow.set_next_tasks(block['values'])
            elif block['type'] == 'condition-block':
                TaskConditionBlock(block['conditions'], workflow).apply(data)
        return data
