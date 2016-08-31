from aiohttp.web_reqrep import FileField
import csv
from io import StringIO
import logging
import re
from uuid import uuid4

from nyuki.api import Response, resource, content_type
from nyuki.workflow.tasks import FACTORY_SCHEMAS


log = logging.getLogger(__name__)


@resource('/workflow/rules', versions=['v1'])
class ApiFactoryRules:

    async def get(self, request):
        return Response(list(FACTORY_SCHEMAS.keys()))


def new_regex(title, pattern, regex_id=None):
    return {
        'id': regex_id or str(uuid4()),
        'title': title,
        'pattern': pattern
    }


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
            regex = new_regex(request['title'], request['pattern'])
        except KeyError as exc:
            return Response(status=400, body={
                'error': 'missing parameter {}'.format(exc)
            })

        await self.nyuki.storage.regexes.insert(regex)
        return Response(regex)

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
        regex = new_regex(
            request.get('title', regex['title']),
            request.get('pattern', regex['pattern']),
            regex_id=regex_id
        )
        await self.nyuki.storage.regexes.insert(regex)
        return Response(regex)

    async def delete(self, request, regex_id):
        """
        Delete the regex with id `regex_id`
        """
        regex = await self.nyuki.storage.regexes.get(regex_id)
        if not regex:
            return Response(status=404)

        await self.nyuki.storage.regexes.delete(regex_id)
        return Response(regex)


def new_lookup(title, table, lookup_id=None):
    """
    Return a lookup representation as:
    {
        'id': '123-456-789',
        'title': 'lookup title',
        'table': [
            {'value': 'this', 'replace': 'that'},
            {'value': 'old', 'replace': 'new'}
        ]
    }
    """
    exc = ValueError('table must be a list of value/replace pairs')
    if not isinstance(table, list):
        raise exc
    for pair in table:
        if 'value' not in pair or 'replace' not in pair:
            raise exc
    return {
        'id': lookup_id or str(uuid4()),
        'title': title,
        'table': table
    }


CSV_FIELDNAMES = ['value', 'replace']


@resource('/workflow/lookups', versions=['v1'])
class ApiFactoryLookups:

    async def get(self, request):
        """
        Return the list of all lookups
        """
        return Response(await self.nyuki.storage.lookups.get_all())

    @content_type('multipart/form-data')
    async def post(self, request):
        """
        Get a CSV file and parse it into a new lookup table.
        """
        data = await request.post()
        if 'csv' not in data or not isinstance(data['csv'], FileField):
            return Response(status=400, body={
                'error': "'csv' field must be a CSV file"
            })

        # From bytes to string (aiohttp handles everything in bytes)
        csv_field = data['csv']
        csv_string = csv_field.file.read()

        # Try utf-8 or latin-1 encoding
        try:
            iocsv = StringIO(csv_string.decode())
        except UnicodeDecodeError:
            iocsv = StringIO(csv_string.decode('latin-1'))

        # Find headers and dialect using a Sniffer
        sniffer = csv.Sniffer()
        sample = iocsv.read(1024)
        iocsv.seek(0)

        try:
            dialect = sniffer.sniff(sample)
        except csv.Error as exc:
            # Could not determine delimiter
            log.error(exc)
            return Response(status=400, body={
                'error': str(exc)
            })

        log.info("CSV file validated with delimiter: '%s'", dialect.delimiter)
        reader = csv.DictReader(iocsv, fieldnames=CSV_FIELDNAMES, dialect=dialect)
        # Ignore header if there is one
        if sniffer.has_header(sample):
            header = reader.__next__()
            log.info('CSV header found: %s', header)
        table = list(reader)

        lookup = new_lookup(csv_field.filename.replace('.csv', ''), table)
        await self.nyuki.storage.lookups.insert(lookup)
        return Response(lookup)

    async def put(self, request):
        """
        Insert a new lookup table
        """
        request = await request.json()

        try:
            lookup = new_lookup(request['title'], request['table'])
        except KeyError as exc:
            return Response(status=400, body={
                'error': 'missing parameter {}'.format(exc)
            })
        except ValueError as exc:
            return Response(status=400, body={
                'error': "'table' must be a list of value/replace pairs"
            })

        await self.nyuki.storage.lookups.insert(lookup)
        return Response(lookup)

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
        lookup = new_lookup(
            request.get('title', lookup['title']),
            request.get('table', lookup['table']),
            lookup_id=lookup_id
        )
        await self.nyuki.storage.lookups.insert(lookup)
        return Response(lookup)

    async def delete(self, request, lookup_id):
        """
        Delete the lookup table with id `lookup_id`
        """
        lookup = await self.nyuki.storage.lookups.get(lookup_id)
        if not lookup:
            return Response(status=404)

        await self.nyuki.storage.lookups.delete(lookup_id)
        return Response(lookup)


@resource('/workflow/lookups/{lookup_id}/csv', versions=['v1'])
class ApiFactoryLookupCSV:

    async def get(self, request, lookup_id):
        """
        Return the lookup table for id `lookup_id`
        """
        lookup = await self.nyuki.storage.lookups.get(lookup_id)
        if not lookup:
            return Response(status=404)

        # Generate filename (escaping spaces and commas)
        filename = '{}.csv'.format(lookup['title'])
        filename = re.sub(r'[ ,]', '_', filename)

        # Write CSV
        with StringIO() as iocsv:
            writer = csv.DictWriter(
                iocsv, fieldnames=CSV_FIELDNAMES, delimiter=','
            )
            writer.writeheader()
            for pair in lookup['table']:
                writer.writerow(pair)
            iocsv.seek(0)

            headers = {
                'Content-Disposition': 'attachment; filename={}'.format(filename),
                'Content-Type': 'text/csv; charset=ISO-8859-1'
            }

            return Response(
                text=iocsv.read(),
                headers=headers
            )
