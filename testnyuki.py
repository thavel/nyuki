import logging

from nyuki.nyuki import Nyuki
from nyuki.messaging.event import on_event, SessionStart, Terminate, MessageReceived


log = logging.getLogger(__name__)


class TestNyuki(Nyuki):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @on_event(SessionStart)
    def _running(self, _):
        log.info('Nyuki is running !')

    @on_event(MessageReceived)
    def _message(self, event):
        log.info('Received : %s', event.message)

    @on_event(Terminate)
    def _terminate(self, _):
        log.info('Nyuki terminated')


if __name__ == '__main__':
    n = TestNyuki()
    n.run()
