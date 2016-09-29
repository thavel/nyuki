import asyncio
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DESCENDING
from pymongo.errors import OperationFailure, DuplicateKeyError

from nyuki.bus import reporting


log = logging.getLogger(__name__)


class DuplicateTemplateError(Exception):
    pass


@contextmanager
def _report_operation(*args, **kwargs):
    try:
        yield
    except OperationFailure as exc:
        reporting.exception(exc)
        raise


async def _index(collection, *args, **kwargs):
    """
    Helper to ensure_index in __init__
    """
    with _report_operation():
        await collection.ensure_index(*args, **kwargs)


class _TemplateCollection:

    """
    Holds all the templates created for tukio, with their versions.
    These records will be used to ensure a persistence of created workflows
    in case the nyuki get into trouble.
    Templates are retrieved and loaded at startup.
    """

    def __init__(self, templates_collection, metadata_collection):
        self._templates = templates_collection
        self._metadata = metadata_collection
        # Indexes (ASCENDING by default)
        asyncio.ensure_future(_index(metadata_collection, 'id', unique=True))
        asyncio.ensure_future(_index(
            templates_collection,
            [('id', DESCENDING), ('version', DESCENDING)],
            unique=True
        ))
        asyncio.ensure_future(_index(
            templates_collection,
            [('id', DESCENDING), ('draft', DESCENDING)]
        ))

    async def get_metadata(self, tid=None):
        """
        Return metadata
        """
        query = {'id': tid} if tid else None
        cursor = self._metadata.find(query, {'_id': 0})

        metadatas = []
        with _report_operation():
            metadatas = await cursor.to_list(None)
        return metadatas

    async def get_all(self, latest=False, draft=False, with_metadata=True):
        """
        Return all templates, used at nyuki's startup and GET /v1/templates
        Fetch latest versions if latest=True
        Fetch drafts if draft=True
        Both drafts and latest version if both are True
        """
        cursor = self._templates.find(None, {'_id': 0})
        cursor.sort('version', DESCENDING)

        templates = []
        with _report_operation():
            templates = await cursor.to_list(None)

        # Collect metadata
        if with_metadata and templates:
            metadatas = await self.get_metadata()
            metadatas = {meta['id']: meta for meta in metadatas}
            for template in templates:
                template.update(metadatas[template['id']])

        if not latest and not draft:
            return templates

        # Retrieve the latest versions + drafts
        lasts = {}
        drafts = []

        for template in templates:
            if draft and template['draft']:
                drafts.append(template)
            elif latest and not template['draft'] and template['id'] not in lasts:
                lasts[template['id']] = template

        return drafts + [tmpl for tmpl in lasts.values()]

    async def get(self, tid, version=None, draft=None, with_metadata=True):
        """
        Return a template's configuration and versions
        """
        query = {'id': tid}

        if version:
            query['version'] = int(version)
        if draft is not None:
            query['draft'] = draft

        cursor = self._templates.find(query, {'_id': 0})
        cursor.sort('version', DESCENDING)

        templates = []
        with _report_operation():
            templates = await cursor.to_list(None)

        # Collect metadata
        if with_metadata and templates:
            metadatas = await self.get_metadata(tid)
            if metadatas:
                for template in templates:
                    template.update(metadatas[0])

        return templates

    async def get_last_version(self, tid):
        """
        Return the highest version of a template
        """
        query = {'id': tid, 'draft': False}
        cursor = self._templates.find(query)
        cursor.sort('version', DESCENDING)

        with _report_operation():
            await cursor.fetch_next

        template = cursor.next_object()
        return template['version'] if template else 0

    async def insert(self, template):
        """
        Insert a template dict, not updatable
        """
        query = {
            'id': template['id'],
            'version': template['version']
        }

        # Remove draft if any
        await self.delete(template['id'], template['version'], True)

        log.info('Insert template with query: %s', query)
        with _report_operation():
            try:
                # Copy dict, mongo somehow alter the given dict
                await self._templates.insert(template.copy())
            except DuplicateKeyError as exc:
                raise DuplicateTemplateError from exc

    async def insert_draft(self, template):
        """
        Check and insert draft, updatable
        """
        query = {
            'id': template['id'],
            'draft': True
        }

        with _report_operation():
            try:
                log.info('Update draft for query: %s', query)
                await self._templates.update(query, template, upsert=True)
            except DuplicateKeyError as exc:
                raise DuplicateTemplateError from exc

    async def insert_metadata(self, metadata):
        """
        Check and insert metadata
        """
        query = {'id': metadata['id']}

        metadata = {
            'id': metadata['id'],
            'title': metadata.get('title', ''),
            'tags': metadata.get('tags', [])
        }

        with _report_operation():
            log.info('Update metadata for query: %s', query)
            await self._metadata.update(query, metadata, upsert=True)

        return metadata

    async def publish_draft(self, tid):
        """
        From draft to production
        """
        query = {'id': tid, 'draft': True}
        with _report_operation():
            await self._templates.update(query, {'$set': {'draft': False}})

    async def delete(self, tid, version=None, draft=None):
        """
        Delete a template from its id with all its versions
        """
        query = {'id': tid}
        if version:
            query['version'] = version
        if draft is not None:
            query['draft'] = draft

        log.info("Removing template(s) with query: %s", query)

        with _report_operation():
            await self._templates.remove(query)
            left = await self._templates.find({'id': tid}).count()
            if not left:
                await self._metadata.remove({'id': tid})


class _DataProcessingCollection:

    def __init__(self, data_collection):
        self._rules = data_collection
        asyncio.ensure_future(_index(data_collection, 'id', unique=True))

    async def get_all(self):
        """
        Return a list of all rules
        """
        cursor = self._rules.find(None, {'_id': 0})
        rules = []
        with _report_operation():
            rules = await cursor.to_list(None)
        return rules

    async def get(self, rule_id):
        """
        Return the rule for given id or None
        """
        cursor = self._rules.find({'id': rule_id}, {'_id': 0})
        with _report_operation():
            await cursor.fetch_next
        return cursor.next_object()

    async def insert(self, data):
        """
        Insert a new data processing rule:
        {
            "id": "rule_id",
            "name": "rule_name",
            "config": {
                "some": "configuration"
            }
        }
        """
        query = {'id': data['id']}
        log.info(
            "Inserting data processing rule in collection '%s'",
            self._rules.name
        )
        log.debug('upserting data: %s', data)
        with _report_operation():
            await self._rules.update(query, data, upsert=True)

    async def delete(self, rule_id=None):
        """
        Delete a rule from its id or all rules
        """
        query = {'id': rule_id} if rule_id is not None else None
        log.info("Removing rule(s) from collection '%s'", self._rules.name)
        log.debug('delete query: %s', query)
        with _report_operation():
            await self._rules.remove(query)


class _InstanceCollection:

    def __init__(self, instances_collection):
        self._instances = instances_collection
        asyncio.ensure_future(_index(self._instances, 'exec.id', unique=True))
        asyncio.ensure_future(_index(self._instances, [('exec.start', DESCENDING)]))
        asyncio.ensure_future(_index(self._instances, [('exec.end', DESCENDING)]))
        asyncio.ensure_future(_index(self._instances, 'exec.state'))

    async def get_one(self, exec_id):
        """
        Return the instance with `exec_id` from workflow history.
        """
        return await self._instances.find_one({'exec.id': exec_id}, {'_id': 0})

    async def get(self, offset=None, limit=None, since=None, state=None):
        """
        Return all instances from history from `since` with state `state`.
        """
        query = {}
        # Prepare query
        if isinstance(since, datetime):
            query['exec.start'] = {'$gte': since}
        if isinstance(state, Enum):
            query['exec.state'] = state.value
        cursor = self._instances.find(query, {'_id': 0})
        # Set offset and limit
        if isinstance(offset, int) and offset >= 0:
            cursor.skip(offset)
        if isinstance(limit, int) and limit > 0:
            cursor.limit(limit)
        cursor.sort('exec.start', DESCENDING)
        # Execute query
        return await cursor.to_list(None)

    async def insert(self, workflow_exec):
        """
        Insert a finished workflow report into the workflow history.
        """
        await self._instances.insert(workflow_exec)


class _TriggerCollection:

    def __init__(self, data_collection):
        self._triggers = data_collection
        asyncio.ensure_future(_index(data_collection, 'tid', unique=True))

    async def get_all(self):
        """
        Return a list of all trigger forms
        """
        cursor = self._triggers.find(None, {'_id': 0})
        triggers = []
        with _report_operation():
            triggers = await cursor.to_list(None)
        return triggers

    async def get(self, template_id):
        """
        Return the trigger form of a given workflow template id
        """
        cursor = self._triggers.find({'tid': template_id}, {'_id': 0})
        with _report_operation():
            await cursor.fetch_next
        return cursor.next_object()

    async def insert(self, tid, form):
        """
        Insert a trigger form for the given workflow template
        """
        data = {'tid': tid, 'form': form}
        with _report_operation():
            await self._triggers.update({'tid': tid}, data, upsert=True)
        return data

    async def delete(self, template_id=None):
        """
        Delete a trigger form
        """
        query = {'tid': template_id} if template_id is not None else None
        with _report_operation():
            await self._triggers.remove(query)


class MongoStorage:

    DEFAULT_DATABASE = 'workflow'

    def __init__(self, host, database=None, **kwargs):
        log.info("Setting up workflow mongo storage with host '%s'", host)
        client = AsyncIOMotorClient(host, **kwargs)
        db_name = database or self.DEFAULT_DATABASE
        db = client[db_name]
        log.info("Workflow database: '%s'", db_name)

        # Collections
        self.templates = _TemplateCollection(db['templates'], db['metadata'])
        self.instances = _InstanceCollection(db['instances'])
        self.regexes = _DataProcessingCollection(db['regexes'])
        self.lookups = _DataProcessingCollection(db['lookups'])
        self.triggers = _TriggerCollection(db['triggers'])
