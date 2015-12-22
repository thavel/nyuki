"""
This is 'timon'
"""
import logging
from nyuki import Nyuki, resource
from nyuki.capabilities import Response


log = logging.getLogger(__name__)


class Timon(Nyuki):

    message = 'hello world!'

    @resource(endpoint='/message')
    class Message:

        def get(self, request):
            return Response({'message': self.message})

        def post(self, request):
            self.message = request['message']
            log.info("message updated to '%s'", self.message)
            self.bus.publish({'order': 'go pumbaa!'})
            return Response(status=200)


if __name__ == '__main__':
    nyuki = Timon()
    nyuki.start()
