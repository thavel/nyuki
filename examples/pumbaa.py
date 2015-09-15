"""
This is 'pumbaa'
"""
import logging
from nyuki import Nyuki, resource, on_event
from nyuki.events import Event
from nyuki.capabilities import Response


log = logging.getLogger(__name__)


class Pumbaa(Nyuki):
    message = 'hello world!'
    def __init__(self):
        super().__init__()
        self.eaten = 0

    @on_event(Event.Connected)
    def on_start(self):
        self.subscribe('timon')

    @on_event(Event.EventReceived)
    def eat_larva(self, event):
        log.info('yummy yummy!')
        self.eaten += 1

    @resource(endpoint='/eaten')
    class Message:
        def get(self, request):
            return Response({'eaten': self.eaten})


if __name__ == '__main__':
    nyuki = Pumbaa()
    nyuki.start()