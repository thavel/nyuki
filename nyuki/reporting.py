import asyncio
from datetime import datetime
from jsonschema import FormatChecker, validate
import logging
from traceback import TracebackException


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
        if not hasattr(publisher, 'subscribe'):
            raise TypeError("Nyuki publisher requires the 'subscribe' method")
        if not hasattr(publisher, 'publish'):
            raise TypeError("Nyuki publisher requires the 'publish' method")

        self.name = name
        self._publisher = publisher
        self._channel = channel
        self._handlers = list()
        asyncio.ensure_future(
            self._publisher.subscribe(channel, self._handle_report)
        )

    async def _handle_report(self, data):
        """
        Handle report, ignore if it comes from this reporter
        """
        if data['author'] == self.name:
            log.debug('Received own report, ignoring')
            return

        tasks = []
        for handler in self._handlers:
            tasks.append(asyncio.ensure_future(handler(data)))

        if not tasks:
            log.debug('No report handler to execute')
            return

        await asyncio.wait(tasks)

    def register_handler(self, handler):
        """
        Register all required handlers for received reports
        """
        if handler in self._handlers:
            # Can't register the same callback twice
            return
        self._handlers.append(handler)

    def check_report(self, report):
        """
        Raise ValidationError on failure
        """
        validate(report, REPORT_SCHEMA, format_checker=report_checker)

    def send_report(self, rtype, data):
        """
        Send reports with a type and any data
        """
        report = {
            'type': rtype,
            'author': self.name,
            'datetime': datetime.utcnow().isoformat(),
            'data': data
        }
        self.check_report(report)
        log.info("Sending report data with type '%s'", rtype)
        asyncio.ensure_future(self._publisher.publish(report, self._channel))

    def exception(self, exc):
        """
        Helper to report an exception traceback from its object
        """
        traceback = TracebackException.from_exception(exc)
        formatted = ''.join(traceback.format())
        log.error(formatted)
        self.send_report('exception', {'traceback': formatted})
