import logging
from nyuki.workflow.tasks.utils import runtime
from tukio.task import register
from tukio.task.holder import TaskHolder


log = logging.getLogger(__name__)


@register('notify', 'execute')
class NotifyTask(TaskHolder):

    SCHEMA = {
        'type': 'object',
        'properties': {
            'topic': {
                'type': 'string',
                'minLength': 1,
                'maxLength': 128
            }
        }
    }

    async def execute(self, event):
        topic = self.config.get('topic')
        log.info('Notifying data to topic: %s', topic)
        await runtime.bus.publish(event.data, topic=topic)
        return event
