"""
This is 'pumbaa'
"""
import logging
from nyuki import Nyuki, resource
from nyuki.capabilities import Response


log = logging.getLogger(__name__)


class Pumbaa(Nyuki):

    message = 'hello world!'

    def __init__(self):
        super().__init__()
        self.eaten = 0

    async def setup(self):
        self.bus.subscribe('timon', self.eat_larva)

    async def eat_larva(self, body):
        log.info('yummy yummy!')
        self.eaten += 1

    @resource(endpoint='/eaten')
    class Eaten:

        def get(self, request):
            return Response({'eaten': self.eaten})


if __name__ == '__main__':
    nyuki = Pumbaa()
    nyuki.start()
