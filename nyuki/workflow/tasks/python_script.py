import logging
from tukio.task import register
from tukio.task.holder import TaskHolder


log = logging.getLogger(__name__)


@register('python_script', 'execute')
class PythonScript(TaskHolder):

    """
    Mainly a testing task
    """

    SCHEMA = {
        'type': 'object',
        'properties': {
            'script': {'type': 'string', 'maxLength': 16384}
        }
    }

    async def execute(self, event):
        if self.config.get('script'):
            eval(self.config.get('script'))
        return event.data
