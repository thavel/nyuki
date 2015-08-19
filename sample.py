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
        @capability(name='last_message')
        def get(self, request):
            return Response({'message': self.message})

        @capability(name='update_message')
        def post(self, request):
            self.message = request['message']
            log.info("Message updated")
            return Response(status=200)

    @resource(endpoint='/alert')
    class Alert:
        @capability(name='alert_someone')
        def post(self, request):
            self.send(request, 'toto@localhost', 'do_something')
            return Response(status=200)


if __name__ == '__main__':
    nyuki = Sample()
    nyuki.start()
