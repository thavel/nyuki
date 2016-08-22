import logging
from nyuki.workflow.tasks.utils import runtime
from tukio.task import register
from tukio.task.holder import TaskHolder


log = logging.getLogger(__name__)


@register('notify', 'execute')
class NotifyTask(TaskHolder):

    """
    A generic task to simply publish data to the bus.
    Might trigger linked workflows across the application.
    """

    async def execute(self, event):
        log.info('Notifying data to the bus')
        await runtime.bus.publish(event.data)
        return event
