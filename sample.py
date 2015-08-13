from nyuki import Nyuki, capability, on_event
from nyuki.event import Event
from nyuki.capability import Response


class Sample(Nyuki):

    def __init__(self):
        super().__init__()
        self.message = 'hello world'

    @on_event(Event.Connected)
    def _on_start(self):
        pass

    @on_event(Event.Disconnected)
    def _on_stop(self):
        pass

    @capability(access='GET', endpoint='/hello')
    def hello(self, request=None):
        return Response(body="Hello world!")

if __name__ == '__main__':
    nyuki = Sample()
    nyuki.start()
