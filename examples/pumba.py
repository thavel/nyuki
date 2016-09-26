"""
This is 'pumba'
"""
import logging
from nyuki import Nyuki, resource, Response


log = logging.getLogger(__name__)


@resource('/eaten', versions=['v1'])
class Eaten:

    async def get(self, request):
        return Response({'eaten': self.nyuki.eaten})


class Pumba(Nyuki):

    HTTP_RESOURCES = Nyuki.HTTP_RESOURCES + [Eaten]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.eaten = 0

    async def setup(self):
        await self.bus.subscribe('timon', self.eat_larva)

    async def eat_larva(self, efrom, data):
        log.info('yummy yummy!')
        self.eaten += 1


if __name__ == '__main__':
    nyuki = Pumba()
    nyuki.start()
