from uuid import uuid4

from nyuki.api import Response, resource
from nyuki.workflow.tasks import FACTORY_SCHEMAS


@resource('/workflow/rules', versions=['v1'])
class ApiFactoryRules:

    async def get(self, request):
        return Response(list(FACTORY_SCHEMAS.keys()))


@resource('/workflow/regexes', versions=['v1'])
class ApiFactoryRegexes:

    async def get(self, request):
        """
        Return the list of all regexes
        """
        return Response(await self.nyuki.storage.regexes.get_all())

    async def put(self, request):
        """
        Insert a new regex
        """
        request = await request.json()

        try:
            data = {
                'id': str(uuid4()),
                'title': request['title'],
                'pattern': request['pattern']
            }
        except KeyError as exc:
            return Response(status=400, body={
                'error': 'missing parameter {}'.format(exc)
            })

        await self.nyuki.storage.regexes.insert(data)
        return Response(data)

    async def delete(self, request):
        """
        Delete all regexes and return the list
        """
        rules = await self.nyuki.storage.regexes.get_all()
        await self.nyuki.storage.regexes.delete()
        return Response(rules)


@resource('/workflow/regexes/{regex_id}', versions=['v1'])
class ApiFactoryRegex:

    async def get(self, request, regex_id):
        """
        Return the regex for id `regex_id`
        """
        regex = await self.nyuki.storage.regexes.get(regex_id)
        if not regex:
            return Response(status=404)
        return Response(regex)

    async def patch(self, request, regex_id):
        """
        Modify an existing regex
        """
        regex = await self.nyuki.storage.regexes.get(regex_id)
        if not regex:
            return Response(status=404)

        request = await request.json()

        data = {
            'id': regex_id,
            'title': request.get('title', regex['title']),
            'pattern': request.get('pattern', regex['pattern'])
        }

        await self.nyuki.storage.regexes.insert(data)
        return Response(data)

    async def delete(self, request, regex_id):
        """
        Delete the regex with id `regex_id`
        """
        regex = await self.nyuki.storage.regexes.get(regex_id)
        if not regex:
            return Response(status=404)

        await self.nyuki.storage.regexes.delete(regex_id)
        return Response(regex)


@resource('/workflow/lookups', versions=['v1'])
class ApiFactoryLookups:

    async def get(self, request):
        """
        Return the list of all lookups
        """
        return Response(await self.nyuki.storage.lookups.get_all())

    async def put(self, request):
        """
        Insert a new lookup table
        """
        request = await request.json()

        try:
            data = {
                'id': str(uuid4()),
                'title': request['title'],
                'table': request['table']
            }
        except KeyError as exc:
            return Response(status=400, body={
                'error': 'missing parameter {}'.format(exc)
            })

        await self.nyuki.storage.lookups.insert(data)
        return Response(data)

    async def delete(self, request):
        """
        Delete all lookups and return the list
        """
        lookups = await self.nyuki.storage.lookups.get_all()
        await self.nyuki.storage.lookups.delete()
        return Response(lookups)


@resource('/workflow/lookups/{lookup_id}', versions=['v1'])
class ApiFactoryLookup:

    async def get(self, request, lookup_id):
        """
        Return the lookup table for id `lookup_id`
        """
        lookup = await self.nyuki.storage.lookups.get(lookup_id)
        if not lookup:
            return Response(status=404)
        return Response(lookup)

    async def patch(self, request, lookup_id):
        """
        Modify an existing lookup table
        """
        lookup = await self.nyuki.storage.lookups.get(lookup_id)
        if not lookup:
            return Response(status=404)

        request = await request.json()

        data = {
            'id': lookup_id,
            'title': request.get('title', lookup['title']),
            'table': request.get('table', lookup['table'])
        }

        await self.nyuki.storage.lookups.insert(data)
        return Response(data)

    async def delete(self, request, lookup_id):
        """
        Delete the lookup table with id `lookup_id`
        """
        lookup = await self.nyuki.storage.lookups.get(lookup_id)
        if not lookup:
            return Response(status=404)

        await self.nyuki.storage.lookups.delete(lookup_id)
        return Response(lookup)
