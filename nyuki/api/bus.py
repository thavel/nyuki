import asyncio

from nyuki.bus.persistence import EventStatus
from nyuki.utils import from_isoformat

from .api import Response, resource


@resource('/bus/replay', versions=['v1'])
class ApiBusReplay:

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
class ApiBusTopics:

    async def get(self, request):
        try:
            self.nyuki._services.get('bus')
        except KeyError:
            return Response(status=404)
        return Response(self.nyuki.bus.public_topics)


@resource('/bus/publish', versions=['v1'])
class ApiBusPublish:

    async def post(self, request):
        try:
            self.nyuki._services.get('bus')
        except KeyError:
            return Response(status=404)
        request = await request.json()
        asyncio.ensure_future(self.nyuki.bus.publish(
            request.get('data', {}), request.get('topic')
        ))
