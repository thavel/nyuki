import logging

from nyuki import Nyuki, capability, on_event
from nyuki.event import Event
from nyuki.capability import Response


log = logging.getLogger(__name__)


class Sample(Nyuki):

    def __init__(self):
        super().__init__()
        self.message = 'Hello world!'

    @on_event(Event.Connected)
    def _on_start(self):
        log.info("Oh great, I'm connected and ready to do what I want!")

    @on_event(Event.Disconnected)
    def _on_stop(self):
        log.info("Alright, this is the end of my existence.")

    @capability(access='GET', endpoint='/hello')
    def hello(self, request=None):
        return Response(body=self.message)

if __name__ == '__main__':
    nyuki = Sample()
    nyuki.start()
