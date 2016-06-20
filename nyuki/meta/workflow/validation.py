import jsonschema
import logging
from tukio import TaskRegistry, UnknownTaskName
from tukio.workflow import WorkflowRootTaskError


log = logging.getLogger(__name__)


class TemplateError(Exception):

    """
    Template error details are formatted in JSON:
    {
        "task_id": "<id>",
        "config_path": "<key.key.key>",
        "error": "<type>",
        "info": "<extra>"
    }
    Any other error is available through `message`.
    """

    def __init__(self, message, details=None):
        self.message = message
        self.details = details or list()

    def as_dict(self):
        return {'message': self.message, 'details': self.details}

    def __str__(self):
        return self.message


def validate(template):
    """
    Validate a template dict and aggregate all errors that could occur.
    Return a tempplate object or raise a ValidationError
    """
    try:
        template.validate()
    except UnknownTaskName as exc:
        log.debug('unknown task: %s', exc)
        raise TemplateError('Unknown task name: {}'.format(exc))
    except WorkflowRootTaskError as exc:
        log.debug('workflow validation error: %s', exc)
        raise TemplateError('Workflow validation error: {}'.format(
            exc
        )) from exc

    errors = list()
    for task in template.as_dict().get('tasks', []):
        err = validate_task(task)
        if err:
            errors.append(err)

    if errors:
        raise TemplateError('Invalid task configurations', details=errors)

    return template


def _get_details(exc, task):
    """
    Gives JSON formatted details for a given exception on a task.
    """
    assert isinstance(exc, jsonschema.ValidationError)

    path = list(exc.absolute_path)
    error = exc.validator
    value = exc.validator_value

    # Get a proper path for the `required` validation error
    if error == 'required':
        cursor = task.get('config', {})
        for key in path:
            cursor = cursor[key]
        for key in value:
            if key not in cursor:
                path.append(key)
                break

    return {
        'task_id': task['id'],
        'config_path': '.'.join(path),
        'error': error,
        'info': value
    }


def validate_task(task):
    """
    Validate the jsonschema configuration of a task
    """
    name = task['name']
    config = task.get('config', {})
    schema = getattr(TaskRegistry.get(name)[0], 'SCHEMA', {})
    try:
        jsonschema.validate(config, schema)
    except jsonschema.ValidationError as exc:
        return _get_details(exc, task)
