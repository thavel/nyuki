import logging

from nyuki import Nyuki, resource, on_event
from nyuki.events import Event
from nyuki.capabilities import Response


log = logging.getLogger(__name__)


class Sample(Nyuki):

    CONF_SCHEMA = {
        'type': 'object',
        'required': ['port'],
        'properties': {
            'port': {
                'type': 'integer',
            }
        }
    }

    def __init__(self):
        super().__init__()
        self.register_schema(self.CONF_SCHEMA)

    @on_event(Event.Connected)
    def _on_start(self):
        log.info("Oh great, I'm connected and ready to do what I want!")
        self.subscribe('sender')

    @resource(endpoint='/message')
    class Message:
        def get(self, request):
            return Response({'message': self.message})

        def post(self, request):
            self.message = request['message']
            log.info("Message updated")
            return Response(status=200)

    @resource(endpoint='/alert')
    class Alert:
        def post(self, request):
            self.send(request, 'toto@localhost', 'do_something')
            return Response(status=200)


if __name__ == '__main__':
    nyuki = Sample()
    nyuki.start()
