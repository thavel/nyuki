import logging
from tukio.task import register
from tukio.task import JoinTask as DefaultJoin


log = logging.getLogger(__name__)


@register('join', 'execute')
class JoinTask(DefaultJoin):

    SCHEMA = {
        'type': 'object',
        'required': ['await_parents'],
        'properties': {
            'update_data_input': {'type': 'boolean'},
            'await_parents': {'type': 'integer'},
        }
    }

    async def execute(self, data, from_parent):
        if not from_parent:
            return
        log.debug('join task {} started.'.format(self))
        self.data_received(data)
        await self.unlock
        if self.config.get('update_data_input', True):
            for call in self.data_stash:
                data.update(call)
        log.debug('join task {} done.'.format(self))
        return data
