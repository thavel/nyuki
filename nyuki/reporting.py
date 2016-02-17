from datetime import datetime
from jsonschema import FormatChecker, validate, ValidationError
import logging


log = logging.getLogger(__name__)


REPORT_SCHEMA = {
    'type': 'object',
    'required': ['type', 'author', 'datetime', 'data'],
    'properties': {
        'type': {
            'type': 'string',
            'minLength': 1
        },
        'author': {
            'type': 'string',
            'minLength': 1
        },
        'datetime': {
            'type': 'string',
            'format': 'isoformat'
        },
        'data': {'type': 'object'}
    },
    "additionalProperties": False
}


def from_isoformat(iso):
    return datetime.strptime(iso, '%Y-%m-%dT%H:%M:%S.%f')


report_checker = FormatChecker()


@report_checker.checks(format='isoformat')
def _check_isoformat(datetime):
    try:
        from_isoformat(datetime)
    except ValueError:
        log.warning('Unknown datetime format: %s', datetime)
        return False
    return True


class Reporter(object):

    def __init__(self, name, publisher, channel):
        if not hasattr(publisher, 'publish'):
            raise TypeError("Nyuki publisher requires the 'publish' method")
        self.name = name
        self._publisher = publisher
        self._channel = channel

    def check_report(self, report):
        """
        Raise ValidationError on failure
        """
        validate(report, REPORT_SCHEMA, format_checker=report_checker)

    async def send_report(self, rtype, data):
        report = {
            'type': rtype,
            'author': self.name,
            'datetime': datetime.utcnow().isoformat(),
            'data': data
        }
        self.check_report(report)
        log.info("Sending report data with type '%s'", rtype)
        await self._publisher.publish(report, self._channel)
