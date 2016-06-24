import asyncio

from nyuki.bus.persistence import EventStatus
from nyuki.utils import from_isoformat

from .capabilities import resource
from .webserver import Response


@resource('/bus/replay', versions=['v1'])
class APIBusReplay:

    async def post(self, request):
        body = await request.json()

        try:
            self.nyuki._services.get('bus')
        except KeyError:
            return Response(status=404)

        # Format 'since' parameter from isoformat
        since = body.get('since')
        if since:
            try:
                since = from_isoformat(since)
            except ValueError:
                return Response({
                    'error': 'Unknown datetime format: %s'.format(since)
                }, status=400)

        # Check and parse event status
        request_status = body.get('status')
        status = list()
        if request_status:
            try:
                if isinstance(request_status, list):
                    for es in request_status:
                        status.append(EventStatus[es])
                else:
                    status.append(EventStatus[request_status])
            except KeyError:
                return Response(status=400, body={
                    'error': 'unknown event status type {}'.format(es)
                })

        await self.nyuki.bus.replay(since, status)


@resource('/bus/topics', versions=['v1'])
class APIBusTopics:

    async def get(self, request):
        return Response(self.nyuki.bus.topics)


@resource('/bus/publish', versions=['v1'])
class BusPublish:

    async def post(self, request):
        await self.BusPublishTopic.post(self, request, None)


@resource('/bus/publish/{topic}', versions=['v1'])
class BusPublishTopic:

    async def post(self, request, topic):
        try:
            self._services.get('bus')
        except KeyError:
            return Response(status=404)

        asyncio.ensure_future(self.bus.publish(
            await request.json(), topic
        ))
