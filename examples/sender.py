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

        def send():
            self.send({'message': 'test'}, 'sample@localhost', 'last_message', callback=replied)

        # def send():
        #     self.send_to_room({'message': 'test'}, 'sample')

        self.event_loop.schedule(1, send)


if __name__ == '__main__':
    n = TestNyuki()
    n.start()
