import logging
from nyuki.transform import Converter
from tukio.task import register
from tukio.task.holder import TaskHolder


log = logging.getLogger(__name__)


@register('factory', 'execute')
class FactoryTask(TaskHolder):

    """
    An base task that can perform some http calls on an API.
    config should be a ruler dictionary:
        {"rulers": [
            {
                "type": <rule-type-name>,
                "rules": [
                    {"fieldname": <name>, ...},
                    {"fieldname": <name>, ...},
                    ...
                ]
            },
            {
                "type": <rule-type-name>,
                "rules": [
                    {"fieldname": <name>, ...},
                    {"fieldname": <name>, ...}
                    ...
                ]
            }
        ]}
        see nyuki transformations.
    """

    async def execute(self, event):
        """
        Factory task that apply regex, lookup, set, unset moves on items.
        """
        data = event.data
        converter = Converter.from_dict(self.config)
        converter.apply(data)
        return data
