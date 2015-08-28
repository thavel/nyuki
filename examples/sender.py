import logging

from nyuki import Nyuki, on_event
from nyuki.events import Event


log = logging.getLogger(__name__)


class TestNyuki(Nyuki):

    @on_event(Event.Connected)
    def _run(self):
        log.info('Sending message')

        def send():
            self.publish({'message': 'test'})

        # def send():
        #     def after(status, response):
        #         log.info('Received status : {}'.format(status))
        #         log.info('Received response : {}'.format(response))
        #     self.request(
        #         None, 'http://localhost:5558/message', 'get',
        #         callback=after)
        #     self.request(
        #         None, 'http://localhost:5558/message', 'post',
        #         data={'message': 'zzzz'}, callback=after)
        #     self.request(
        #         None, 'http://localhost:5558/message', 'get',
        #         callback=after)

        self.event_loop.schedule(1, send)
        self.event_loop.schedule(2, send)


if __name__ == '__main__':
    n = TestNyuki()
    n.start()
