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

    NAME = 'factory'

    async def execute(self, data):
        """
        Factory task that apply regex, lookup, set, unset moves on items.
        """
        converter = Converter.from_dict(self.config)
        converter.apply(data)
        return data
