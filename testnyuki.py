import logging

from nyuki.nyuki import Nyuki
from nyuki.messaging.event import on_event, SessionStart


log = logging.getLogger(__name__)


class TestNyuki(Nyuki):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @on_event(SessionStart)
    def _running(self, event):
        log.info('Nyuki is running !')


if __name__ == '__main__':
    n = TestNyuki()
    n.run()
