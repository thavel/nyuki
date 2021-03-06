import asyncio
from datetime import datetime
from functools import partial
from jsonschema import FormatChecker, validate, ValidationError
import logging
import os
import socket
import sys
from traceback import TracebackException

from nyuki.utils import from_isoformat


log = logging.getLogger(__name__)


REPORT_SCHEMA = {
    'type': 'object',
    'required': ['hostname', 'ipv4', 'type', 'author', 'datetime', 'data'],
    'properties': {
        'hostname': {
            'type': 'string',
            'minLength': 1
        },
        'ipv4': {
            'type': 'string',
            'minLength': 1
        },
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

    """
    Mqtt and Xmpp bus are handled differently as the topics mechanism
    is not the same.
    """

    EXCEPTION_TTL = 3600
    MONIT_TOPIC = '+/monitoring'

    def __init__(self):
        self._name = None
        self._loop = None
        self._publisher = None
        self._channel = None
        self._handler = None
        self._last_exceptions = list()

    def init(self, name, publisher, loop=None):
        self._name = name
        self._loop = loop or asyncio.get_event_loop()
        self._publisher = publisher
        self._service = self._publisher.SERVICE

        if self._service == 'xmpp':
            self._channel = 'monitoring'
        elif self._service == 'mqtt':
            self._channel = self.MONIT_TOPIC.replace('+', self._name)
        else:
            raise TypeError('Nyuki publisher must be XmppBus or MqttBus')

    async def _handle_report(self, topic, data):
        """
        Handle XMPP report, ignore if it comes from this reporter
        """
        if self._handler is None:
            log.debug('Report received, no handler set')
            return

        try:
            self.check_report(data)
        except ValidationError:
            log.debug('Received invalid report format, ignoring')
            return

        if data['author'] == self._name:
            log.debug('Received own report, ignoring')
            return

        await self._handler(topic, data)

    def register_handler(self, handler):
        """
        Register all required handlers for received reports
        """
        if not asyncio.iscoroutinefunction(handler):
            raise ValueError('handler must be a coroutine')
        if self._service == 'mqtt':
            asyncio.ensure_future(self._publisher.subscribe(
                self.MONIT_TOPIC, self._handle_report
            ))
        self._handler = handler

    def check_report(self, report):
        """
        Raise ValidationError on failure
        """
        validate(report, REPORT_SCHEMA, format_checker=report_checker)

    def send_report(self, rtype, data):
        """
        Send reports with a type and any data

        Using docker/fleet, we require some informations about IP/hostname of
        our nyuki containers, using environnement vars :
            - MACHINE_NAME: machine hostname
            - DEFAULT_IPV4: local container ipv4
        Otherwise, the nyuki try and search for it by itself.
        """
        if not self._publisher:
            log.warning('Reporting not initiated')
            return

        report = {
            'hostname': os.environ.get('MACHINE_NAME', socket.gethostname()),
            'ipv4': os.environ.get(
                'DEFAULT_IPV4',
                socket.gethostbyname(socket.gethostname())
            ),
            'type': rtype,
            'author': self._name,
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

        if formatted in self._last_exceptions:
            log.debug('Exception already logged')
            return

        # Retain the formatted exception in memory to avoid looping
        self._last_exceptions.append(formatted)
        self._loop.call_later(
            self.EXCEPTION_TTL, self._forget_exception, formatted
        )

        self.send_report('exception', {'traceback': formatted})

    def _forget_exception(self, formatted):
        self._last_exceptions.remove(formatted)


sys.modules[__name__] = Reporter()
