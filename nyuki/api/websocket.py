from .capabilities import resource
from .webserver import Response


@resource('/websocket', versions=['v1'])
class ApiWebsocketToken:

    def get(self, request):
        try:
            self.nyuki._services.get('websocket')
        except KeyError:
            return Response(status=404)

        token = self.nyuki.websocket.new_token()
        return Response({'token': token})
