import logging

from nyuki import Nyuki, on_event
from nyuki.events import Event


log = logging.getLogger(__name__)


class TestNyuki(Nyuki):

    @on_event(Event.Connected)
    def _run(self):
        log.info('Sending message')

        def replied(response):
            log.info('Received response : {}'.format(response))
            self.stop()

        self.send(
            {'message': 'test'}, 'sample@localhost', 'update_message',
            callback=replied)


if __name__ == '__main__':
    n = TestNyuki()
    n.start()
