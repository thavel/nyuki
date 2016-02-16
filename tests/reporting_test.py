from asynctest import TestCase, CoroutineMock, ignore_loop
from datetime import datetime
from jsonschema import ValidationError
from nose.tools import assert_raises, eq_

from nyuki.reporting import Reporter


class ReportingTest(TestCase):

    def setUp(self):
        self.publisher = CoroutineMock()
        self.reporter = Reporter('test', self.publisher, 'errors')

    @ignore_loop
    def test_001_check_schema(self):
        with assert_raises(ValidationError):
            self.reporter.check_report({
                'type': 'something',
                'author': 'test',
                'datetime': 'nope',
                'data': {
                    'address': 'test',
                    'traceback': 'test'
                }
            })

        self.reporter.check_report({
            'type': 'something',
            'author': 'test',
            'datetime': datetime.utcnow().isoformat(),
            'data': {
                'address': 'test',
                'traceback': 'test'
            }
        })

    async def test_002_check_send_report(self):
        with assert_raises(ValidationError):
            await self.reporter.send_report('type', 'nope')
        await self.reporter.send_report('type', {'key': 'value'})
        # Troubles patching datetime.utcnow
        eq_(self.publisher.publish.call_count, 1)