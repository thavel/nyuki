import asyncio
import logging

from nyuki.messaging.event import on_event, SessionStart, Terminate
from nyuki.nyuki import Nyuki


log = logging.getLogger(__name__)


class TestNyuki(Nyuki):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.count = 0

    @on_event(SessionStart)
    def _running(self, _):
        self.loop.add_timeout('yo', 3, self.func)
        log.info('Nyuki is running with %s', self.loop)

    def func(self):
        self.count += 1
        self.loop.schedule(3, self.func)
        log.info("after 3 seconds : %s", self.count)

    @on_event(Terminate)
    def _terminated(self, _):
        log.info('Nyuki terminated')


if __name__ == '__main__':
    n = TestNyuki()
    n.run()
