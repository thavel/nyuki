"""
This is 'timon'
"""
import logging
from nyuki import Nyuki, resource, Response


log = logging.getLogger(__name__)


@resource('/message', versions=['v1'])
class Message:

    async def get(self, request):
        return Response({'message': self.nyuki.message})

    async def put(self, request):
        request = await request.json()
        self.nyuki.message = request['message']
        log.info("message updated to '%s'", self.nyuki.message)
        await self.nyuki.bus.publish({'order': 'go pumbaa!'})
        # No 'return' implies 200 Ok


class Timon(Nyuki):

    HTTP_RESOURCES = Nyuki.HTTP_RESOURCES + [Message]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.message = 'hello world!'


if __name__ == '__main__':
    nyuki = Timon()
    nyuki.start()
