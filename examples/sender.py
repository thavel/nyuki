import logging
import asyncio

from nyuki import Nyuki, on_event
from nyuki.events import Event


log = logging.getLogger(__name__)


class TestNyuki(Nyuki):

    @on_event(Event.Connected)
    def _run(self):
        log.info('Sending message')

        # def send():
        #     self.publish({'message': 'test'})

        def send():
            def after(response):
                if isinstance(response, Exception):
                    log.error('got exception: {}'.format(response))
                else:
                    log.info('received response: {}'.format(response.json))
            asyncio.async(self.request(None, 'http://localhost:5558/message',
                                       'get', callback=after, out=True))
            asyncio.async(self.request(None, 'http://localhost:5558/message',
                                       'post', data={'message': 'zzzz'},
                                       callback=after, out=True))
            asyncio.async(self.request(None, 'http://localhost:5559/message',
                                       'get', callback=after, out=True))

        self.loop.call_later(2, send)


if __name__ == '__main__':
    n = TestNyuki()
    n.start()
