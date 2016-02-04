from datetime import datetime
from enum import Enum
from jsonschema import FormatChecker, validate, ValidationError
import logging


log = logging.getLogger(__name__)


class ReportTypes(Enum):

    error = {
        'type': 'object',
        'required': ['code', 'message'],
        'properties': {
            'code': {
                'type': 'string',
                'minLength': 1
            },
            'message': {
                'type': 'string',
                'minLength': 1
            }
        },
        "additionalProperties": False
    }

    connection_lost = {
        'type': 'object',
        'required': ['address'],
        'properties': {
            'address': {
                'type': 'string',
                'minLength': 1
            }
        },
        "additionalProperties": False
    }

    @classmethod
    def all(cls):
        return [item.name for item in cls]


REPORT_SCHEMA = {
    'type': 'object',
    'required': ['type', 'author', 'date', 'data'],
    'properties': {
        'type': {
            'type': 'string',
            'format': 'report_type'
        },
        'author': {
            'type': 'string',
            'minLength': 1
        },
        'date': {
            'type': 'string',
            'format': 'isoformat'
        },
        'data': {'oneOf': [
            {'$ref': '#/definitions/{}'.format(rtype)} for rtype in ReportTypes.all()
        ]}
    },
    "additionalProperties": False,
    'definitions': {rtype: ReportTypes[rtype].value for rtype in ReportTypes.all()}
}


def from_isoformat(iso):
    return datetime.strptime(iso, '%Y-%m-%dT%H:%M:%S.%f')


report_checker = FormatChecker()


@report_checker.checks(format='report_type')
def _check_report_type(rtype):
    if rtype not in ReportTypes.all():
        log.warning('Unknown report type: %s', rtype)
        return False
    return True


@report_checker.checks(format='isoformat')
def _check_isoformat(date):
    try:
        from_isoformat(date)
    except ValueError:
        log.warning('Unknown date format: %s', date)
        return False
    return True


class Reporter(object):

    def __init__(self, name, publisher):
        if not hasattr(publisher, 'publish'):
            raise TypeError("Nyuki publisher requires the 'publish' method")
        self._name = name
        self._publisher = publisher

    def check_report(self, report):
        """
        Raise ValidationError on failure
        """
        validate(report, REPORT_SCHEMA, format_checker=report_checker)

    async def _send_report(self, rtype, data):
        assert rtype in ReportTypes.all()
        report = {
            'type': rtype,
            'author': self._name,
            'date': datetime.utcnow().isoformat(),
            'data': data
        }

        try:
            self.check_report(report)
        except ValidationError as ve:
            log.exception(ve)
            log.error('Report validation failed: %s', str(ve))
            return

        log.info('Sending report data: %s', report)
        await self._publisher.publish(report, 'reports')

    async def connection_lost(self, address):
        await self._send_report('connection_lost', {
            'address': address
        })

    async def error(self, code, message):
        await self._send_report('error', {
            'code': code,
            'message': message
        })
