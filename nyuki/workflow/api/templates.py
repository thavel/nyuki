import asyncio
import logging
from pymongo import DESCENDING
from pymongo.errors import AutoReconnect, DuplicateKeyError
from tukio.workflow import TemplateGraphError, WorkflowTemplate

from nyuki.api import Response, resource
from nyuki.workflow.validation import validate, TemplateError


log = logging.getLogger(__name__)


class ConflictError(Exception):
    pass


class DuplicateTemplateError(Exception):
    pass


class TemplateCollection:

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
        asyncio.ensure_future(self._metadata.create_index('id', unique=True))
        asyncio.ensure_future(self._templates.create_index(
            [('id', DESCENDING), ('version', DESCENDING)],
            unique=True
        ))
        asyncio.ensure_future(self._templates.create_index(
            [('id', DESCENDING), ('draft', DESCENDING)]
        ))

    async def get_metadata(self, tid=None):
        """
        Return metadata
        """
        query = {'id': tid} if tid else None
        cursor = self._metadata.find(query, {'_id': 0})
        return await cursor.to_list(None)

    async def get_all(self, full=False, latest=False, draft=False, with_metadata=True):
        """
        Return all templates, used at nyuki's startup and GET /v1/templates
        Fetch latest versions if latest=True
        Fetch drafts if draft=True
        Both drafts and latest version if both are True
        """
        filters = {'_id': 0}
        # '/v1/workflow/templates' does not requires all the informations
        if full is False:
            filters.update({'id': 1, 'draft': 1, 'version': 1, 'topics': 1})

        cursor = self._templates.find(None, filters)
        cursor.sort('version', DESCENDING)
        templates = await cursor.to_list(None)

        # Collect metadata
        if with_metadata and templates:
            metadatas = await self.get_metadata()
            metadatas = {meta['id']: meta for meta in metadatas}
            for template in templates:
                template.update(metadatas[template['id']])

        if latest is False and draft is False:
            return templates

        # Retrieve the latest versions + drafts
        lasts = {}
        drafts = []

        for template in templates:
            if draft and template['draft']:
                drafts.append(template)
            elif latest and not template['draft'] and template['id'] not in lasts:
                lasts[template['id']] = template

        return drafts + list(lasts.values())

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

        log.info('Update metadata for query: %s', query)
        await self._metadata.update(query, metadata, upsert=True)

        return metadata

    async def publish_draft(self, tid):
        """
        From draft to production
        """
        query = {'id': tid, 'draft': True}
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

        await self._templates.remove(query)
        left = await self._templates.find({'id': tid}).count()
        if not left:
            await self._metadata.remove({'id': tid})


@resource('/workflow/tasks', versions=['v1'])
class ApiTasks:

    async def get(self, request):
        """
        Return the available tasks
        """
        return Response(self.nyuki.AVAILABLE_TASKS)


class _TemplateResource:

    """
    Share methods between templates resources
    """

    async def update_draft(self, template, from_request=None):
        """
        Helper to insert/update a draft
        """
        tmpl_dict = template.as_dict()

        # Auto-increment version, draft only
        last_version = await self.nyuki.storage.templates.get_last_version(
            template.uid
        )
        tmpl_dict['version'] = last_version + 1
        tmpl_dict['draft'] = True

        # Store task extra info (ie. title)
        if from_request is not None:
            rqst_tasks = from_request.get('tasks', [])
            tmpl_tasks = tmpl_dict['tasks']
            for src in rqst_tasks:
                match = list(filter(lambda t: t['id'] == src['id'], tmpl_tasks))
                if match:
                    match[0].update({'title': src.get('title')})

        try:
            await self.nyuki.storage.templates.insert_draft(tmpl_dict)
        except DuplicateTemplateError as exc:
            raise ConflictError('Template already exists for this version') from exc

        return tmpl_dict

    def errors_from_validation(self, template):
        """
        Validate and return the list of errors if any
        """
        errors = None
        try:
            validate(template)
        except TemplateError as err:
            errors = err.as_dict()
        return errors


@resource('/workflow/templates', versions=['v1'])
class ApiTemplates(_TemplateResource):

    async def get(self, request):
        """
        Return available workflows' DAGs
        """
        try:
            templates = await self.nyuki.storage.templates.get_all(
                full=(request.GET.get('full') == '1'),
                latest=(request.GET.get('latest') == '1'),
                draft=(request.GET.get('draft') == '1'),
            )
        except AutoReconnect:
            return Response(status=503)
        return Response(templates)

    async def put(self, request):
        """
        Create a workflow DAG from JSON
        """
        request = await request.json()

        if 'id' in request:
            try:
                draft = await self.nyuki.storage.templates.get(
                    request['id'], draft=True
                )
            except AutoReconnect:
                return Response(status=503)
            if draft:
                return Response(status=409, body={
                    'error': 'draft already exists'
                })

        if self.nyuki.DEFAULT_POLICY is not None and 'policy' not in request:
            request['policy'] = self.nyuki.DEFAULT_POLICY

        try:
            template = WorkflowTemplate.from_dict(request)
        except TemplateGraphError as exc:
            return Response(status=400, body={
                'error': str(exc)
            })

        try:
            metadata = await self.nyuki.storage.templates.get_metadata(template.uid)
        except AutoReconnect:
            return Response(status=503)
        if not metadata:
            if 'title' not in request:
                return Response(status=400, body={
                    'error': "workflow 'title' key is mandatory"
                })

            metadata = {
                'id': template.uid,
                'title': request['title'],
                'tags': request.get('tags', [])
            }

            await self.nyuki.storage.templates.insert_metadata(metadata)
        else:
            metadata = metadata[0]

        try:
            tmpl_dict = await self.update_draft(template, request)
        except ConflictError as exc:
            return Response(status=409, body={
                'error': exc
            })

        return Response({
            **tmpl_dict,
            **metadata,
            'errors': self.errors_from_validation(template)
        })


@resource('/workflow/templates/{tid}', versions=['v1'])
class ApiTemplate(_TemplateResource):

    async def get(self, request, tid):
        """
        Return the latest version of the template
        """
        try:
            tmpl = await self.nyuki.storage.templates.get(tid)
        except AutoReconnect:
            return Response(status=503)
        if not tmpl:
            return Response(status=404)

        return Response(tmpl)

    async def put(self, request, tid):
        """
        Create a new draft for this template id
        """
        try:
            versions = await self.nyuki.storage.templates.get(tid)
        except AutoReconnect:
            return Response(status=503)
        if not versions:
            return Response(status=404)

        for v in versions:
            if v['draft'] is True:
                return Response(status=409, body={
                    'error': 'This draft already exists'
                })

        request = await request.json()

        try:
            # Set template ID from url
            template = WorkflowTemplate.from_dict({**request, 'id': tid})
        except TemplateGraphError as exc:
            return Response(status=400, body={
                'error': str(exc)
            })

        try:
            tmpl_dict = await self.update_draft(template, request)
        except ConflictError as exc:
            return Response(status=409, body={
                'error': exc
            })

        metadata = await self.nyuki.storage.templates.get_metadata(template.uid)
        metadata = metadata[0]

        return Response({
            **tmpl_dict,
            **metadata,
            'errors': self.errors_from_validation(template)
        })

    async def patch(self, request, tid):
        """
        Modify the template's metadata
        """
        try:
            tmpl = await self.nyuki.storage.templates.get(tid)
        except AutoReconnect:
            return Response(status=503)
        if not tmpl:
            return Response(status=404)

        request = await request.json()

        # Add ID, request dict cleaned in storage
        metadata = await self.nyuki.storage.templates.insert_metadata({
            **request,
            'id': tid
        })

        return Response(metadata)

    async def delete(self, request, tid):
        """
        Delete the template
        """
        try:
            tmpl = await self.nyuki.storage.templates.get(tid)
        except AutoReconnect:
            return Response(status=503)
        if not tmpl:
            return Response(status=404)

        await self.nyuki.storage.templates.delete(tid)
        await self.nyuki.storage.triggers.delete(tid)

        try:
            await self.nyuki.engine.unload(tid)
        except KeyError as exc:
            log.debug(exc)

        return Response(tmpl)


@resource('/workflow/templates/{tid}/{version:\d+}', versions=['v1'])
class ApiTemplateVersion(_TemplateResource):

    async def get(self, request, tid, version):
        """
        Return the template's given version
        """
        try:
            tmpl = await self.nyuki.storage.templates.get(tid, version, False)
        except AutoReconnect:
            return Response(status=503)
        if not tmpl:
            return Response(status=404)

        return Response(tmpl)

    async def delete(self, request, tid, version):
        """
        Delete a template with given version
        """
        try:
            tmpl = await self.nyuki.storage.templates.get(tid)
        except AutoReconnect:
            return Response(status=503)
        if not tmpl:
            return Response(status=404)

        await self.nyuki.storage.templates.delete(tid, version)
        return Response(tmpl[0])


@resource('/workflow/templates/{tid}/draft', versions=['v1'])
class ApiTemplateDraft(_TemplateResource):

    async def get(self, request, tid):
        """
        Return the template's draft, if any
        """
        try:
            tmpl = await self.nyuki.storage.templates.get(tid, draft=True)
        except AutoReconnect:
            return Response(status=503)
        if not tmpl:
            return Response(status=404)

        return Response(tmpl[0])

    async def post(self, request, tid):
        """
        Publish a draft into production
        """
        try:
            tmpl = await self.nyuki.storage.templates.get(tid, draft=True)
        except AutoReconnect:
            return Response(status=503)
        if not tmpl:
            return Response(status=404)

        draft = {
            **tmpl[0],
            'draft': False
        }

        try:
            # Set template ID from url
            template = WorkflowTemplate.from_dict({**draft, 'draft': False})
        except TemplateGraphError as exc:
            return Response(status=400, body={
                'error': str(exc)
            })

        errors = self.errors_from_validation(template)
        if errors is not None:
            return Response(status=400, body=errors)

        await self.nyuki.engine.load(template)
        # Update draft into a new template
        await self.nyuki.storage.templates.publish_draft(tid)
        return Response(draft)

    async def patch(self, request, tid):
        """
        Modify the template's draft
        """
        try:
            tmpl = await self.nyuki.storage.templates.get(tid, draft=True)
        except AutoReconnect:
            return Response(status=503)
        if not tmpl:
            return Response(status=404)

        request = await request.json()

        try:
            # Set template ID from url
            template = WorkflowTemplate.from_dict({**request, 'id': tid})
        except TemplateGraphError as exc:
            return Response(status=400, body={
                'error': str(exc)
            })

        try:
            tmpl_dict = await self.update_draft(template, request)
        except ConflictError as exc:
            return Response(status=409, body={
                'error': str(exc)
            })

        metadata = await self.nyuki.storage.templates.get_metadata(template.uid)
        metadata = metadata[0]

        return Response({
            **tmpl_dict,
            **metadata,
            'errors': self.errors_from_validation(template)
        })

    async def delete(self, request, tid):
        """
        Delete the template's draft
        """
        try:
            tmpl = await self.nyuki.storage.templates.get(tid, draft=True)
        except AutoReconnect:
            return Response(status=503)
        if not tmpl:
            return Response(status=404)

        await self.nyuki.storage.templates.delete(tid, draft=True)
        return Response(tmpl[0])
