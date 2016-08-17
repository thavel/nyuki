from tukio.task.join import JoinTask

from .factory import FactoryTask, FACTORY_SCHEMAS
from .notify import NotifyTask
from .python_script import PythonScript
from .report import ReportTask
from .sleep import SleepTask
from .task_selector import TaskSelector


# Add a schema to the join task
JoinTask.SCHEMA = {
    'type': 'object',
    'required': ['wait_for'],
    'properties': {
        'wait_for': {
            'anyOf': [
                {
                    'type': 'array',
                    'minItems': 2,
                    'maxItems': 64,
                    'uniqueItems': True,
                    'items': {
                        'type': 'string',
                        'minLength': 1,
                        'maxLength': 1024
                    }
                },
                {'type': 'integer', 'minimum': 2}
            ]
        },
        'timeout': {'type': 'integer', 'minimum': 1}
    }
}

# Generic schema to reference a task ID
TASKID_SCHEMA = {
    'type': 'string',
    'description': 'task_id',
    'maxLength': 128
}
