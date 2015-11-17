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
        self.messages = {
            '1': 'message 1',
            '2': 'message 2'
        }

    def setup(self):
        log.info("Oh great, I'm connected and ready to do what I want!")

    @on_event(Event.Connected)
    def _on_start(self):
        self.subscribe('sender')

    @resource(endpoint='/message')
    class Messages:
        def get(self, request):
            return Response(self.messages)

        def post(self, request):
            self.messages.update(request)
            return Response(self.messages)

    @resource(endpoint=r'/message/{mid:\d+}')
    class Message:
        def get(self, request, mid):
            if mid not in self.messages:
                return Response(status=404,
                                body={'message': 'message does not exists'})
            return Response({'message': self.messages[mid]})

        def patch(self, request, mid):
            try:
                self.messages[mid] = request['message']
            except KeyError:
                return Response(status=400,
                                body={'message': 'missing message'})
            return Response(
                status=200,
                body={'message': self.messages[mid]}
            )

    def teardown(self):
        log.info('goodbye !')


if __name__ == '__main__':
    nyuki = Sample()
    nyuki.start()
