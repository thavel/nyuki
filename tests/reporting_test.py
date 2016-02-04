from asynctest import TestCase, CoroutineMock, ignore_loop
from datetime import datetime
from jsonschema import ValidationError
from nose.tools import assert_raises, eq_

from nyuki.reporting import Reporter


class ReportingTest(TestCase):

    def setUp(self):
        self.publisher = CoroutineMock()
        self.reporter = Reporter('test', self.publisher)

    @ignore_loop
    def test_001_check_type(self):
        with assert_raises(ValidationError):
            self.reporter.check_report({
                'type': 'something',
                'author': 'test',
                'date': datetime.utcnow().isoformat(),
                'data': {
                    'address': 'test'
                }
            })

    @ignore_loop
    def test_002_check_isoformat(self):
        with assert_raises(ValidationError):
            self.reporter.check_report({
                'type': 'connection_lost',
                'author': 'test',
                'date': 'nope',
                'data': {
                    'address': 'test'
                }
            })

    async def test_003_check_error_format(self):
        with assert_raises(ValidationError):
            self.reporter.check_report({
                'type': 'error',
                'author': 'test',
                'date': datetime.utcnow().isoformat(),
                'data': {
                    'code': 'test'
                }
            })
        self.reporter.check_report({
            'type': 'error',
            'author': 'test',
            'date': datetime.utcnow().isoformat(),
            'data': {
                'code': 'test',
                'message': 'test'
            }
        })
        await self.reporter.error('123', 'test')
        # Troubles patching datetime.utcnow
        eq_(self.publisher.publish.call_count, 1)

    async def test_004_check_connection_lost_format(self):
        with assert_raises(ValidationError):
            self.reporter.check_report({
                'type': 'connection_lost',
                'author': 'test',
                'date': datetime.utcnow().isoformat(),
                'data': {}
            })
        self.reporter.check_report({
            'type': 'connection_lost',
            'author': 'test',
            'date': datetime.utcnow().isoformat(),
            'data': {
                'address': 'test'
            }
        })
        await self.reporter.connection_lost('test')
        # Troubles patching datetime.utcnow
        eq_(self.publisher.publish.call_count, 1)
