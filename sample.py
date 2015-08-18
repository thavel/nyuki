import logging

from nyuki import Nyuki, on_event, resource, capability
from nyuki.events import Event
from nyuki.capabilities import Response


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

    @resource(endpoint='/message')
    class Message:
        @capability(name='list_messages')
        def get(self, request):
            return Response(body=self.message)


if __name__ == '__main__':
    nyuki = Sample()
    nyuki.start()