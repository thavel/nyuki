import logging

from nyuki.eventloop import EventLoop
from nyuki.messaging.event import on_event, SessionStart, Terminate, MessageReceived
from nyuki.nyuki import Nyuki


log = logging.getLogger(__name__)


class TestNyuki(Nyuki):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop = EventLoop()
        self.count = 0

    @on_event(SessionStart)
    def _running(self, _):
        log.info('Nyuki is running with %s', self.loop)
        self.loop.start()
        self.func()

    def func(self):
        self.count += 1
        self.loop.schedule(3, self.func)
        log.info("after 5 seconds : %s", self.count)

    @on_event(MessageReceived)
    def _message(self, event):
        log.info('Received : %s', event.message)

    @on_event(Terminate)
    def _terminate(self, _):
        self.loop.stop()
        log.info('Nyuki terminated')


if __name__ == '__main__':
    n = TestNyuki()
    n.run()
