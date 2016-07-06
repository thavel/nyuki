import asyncio
from datetime import datetime
import functools
import json
import logging
from tukio import Engine, Workflow, WorkflowTemplate, TaskRegistry
from tukio.workflow import TemplateGraphError
from uuid import uuid4

from nyuki import Nyuki, resource, Response
from nyuki.bus import reporting
from .storage import MongoStorage, DuplicateTemplateError
from .tasks import *
from .validation import validate, TemplateError


log = logging.getLogger(__name__)


class BadRequestError(Exception):
    pass


class ConflictError(Exception):
    pass


class WorkflowNyuki(Nyuki):

    """
    Generic workflow nyuki allowing data storage and manipulation
    of tukio's workflows.
    https://github.com/optiflows/tukio
    """

    CONF_SCHEMA = {
        'type': 'object',
        'required': ['mongo'],
        'properties': {
            'mongo': {
                'type': 'object',
                'required': ['host'],
                'properties': {
                    'host': {'type': 'string', 'minLength': 1},
                    'database': {'type': 'string', 'minLength': 1}
                }
            },
            'topics': {
                'type': 'array',
                'items': {'type': 'string', 'minLength': 1}
            }
        }
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.register_schema(self.CONF_SCHEMA)
        self.migrate_config()
        self.engine = None
        self.storage = None

        self.AVAILABLE_TASKS = {}
        for name, value in TaskRegistry.all().items():
            self.AVAILABLE_TASKS[name] = getattr(value[0], 'SCHEMA', {})

    @property
    def mongo_config(self):
        return self.config['mongo']

    @property
    def topics(self):
        return self.config.get('topics', [])

    async def setup(self):
        self.engine = Engine(loop=self.loop)
        await self.reload_from_storage()
        for topic in self.topics:
            asyncio.ensure_future(self.bus.subscribe(
                topic, asyncio.coroutine(functools.partial(
                    self.workflow_event, efrom=topic
                ))
            ))

    async def reload(self):
        await self.reload_from_storage()

    async def teardown(self):
        if self.engine:
            await self.engine.stop()

    async def workflow_event(self, data, efrom=None):
        await self.engine.data_received(data, efrom)

    async def reload_from_storage(self):
        """
        Check mongo, retrieve and load all templates
        """
        self.storage = MongoStorage(**self.mongo_config)

        templates = await self.storage.templates.get_all(
            latest=True,
            with_metadata=False
        )

        for template in templates:
            try:
                await self.engine.load(WorkflowTemplate.from_dict(template))
            except Exception as exc:
                # Means a bad workflow is in database, report it
                reporting.exception(exc)

    async def api_new_draft(self, template):
        """
        Helper to insert/update a draft
        """
        tmpl_dict = template.as_dict()
        # Auto-increment version, draft only
        last_version = await self.storage.templates.get_last_version(template.uid)
        tmpl_dict['version'] = last_version + 1
        tmpl_dict['draft'] = True

        try:
            await self.storage.templates.insert_draft(tmpl_dict)
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

    @resource('/workflow/templates', version='v1')
    class Templates:

        async def get(self, request):
            """
            Return available workflows' DAGs
            """
            return Response(await self.storage.templates.get_all(
                latest=request.GET.get('latest') in ['true', 'True'],
                draft=request.GET.get('draft') in ['true', 'True'],
            ))

        async def put(self, request):
            """
            Create a workflow DAG from JSON
            """
            request = await request.json()

            if 'id' in request:
                if await self.storage.templates.get(request['id'], draft=True):
                    return Response(status=409, body={
                        'error': 'draft already exists'
                    })

            try:
                template = WorkflowTemplate.from_dict(request)
            except TemplateGraphError as exc:
                return Response(status=400, body={
                    'error': str(exc)
                })

            metadata = await self.storage.templates.get_metadata(template.uid)
            if not metadata:
                if 'title' not in request:
                    return Response(status=400, body={
                        'error': "workflow 'title' key is mandatory"
                    })

                metadata = {
                    'id': template.uid,
                    'title': request['title'],
                    'description': request.get('description', ''),
                    'tags': request.get('tags', [])
                }

                await self.storage.templates.insert_metadata(metadata)
            else:
                metadata = metadata[0]

            try:
                tmpl_dict = await self.api_new_draft(template)
            except ConflictError as exc:
                return Response(status=409, body={
                    'error': exc
                })

            return Response({
                **tmpl_dict,
                **metadata,
                'errors': self.errors_from_validation(template)
            })

    @resource('/workflow/templates/{tid}', version='v1')
    class Template:

        async def get(self, request, tid):
            """
            Return the latest version of the template
            """
            tmpl = await self.storage.templates.get(tid)
            if not tmpl:
                return Response(status=404)

            return Response(tmpl)

        async def put(self, request, tid):
            """
            Create a new draft for this template id
            """
            versions = await self.storage.templates.get(tid)
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
                tmpl_dict = await self.api_new_draft(template)
            except ConflictError as exc:
                return Response(status=409, body={
                    'error': exc
                })

            metadata = await self.storage.templates.get_metadata(template.uid)
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
            tmpl = await self.storage.templates.get(tid)
            if not tmpl:
                return Response(status=404)

            request = await request.json()

            # Add ID, request dict cleaned in storage
            metadata = await self.storage.templates.insert_metadata({
                **request,
                'id': tid
            })

            return Response(metadata)

        async def delete(self, request, tid):
            """
            Delete the template
            """
            tmpl = await self.storage.templates.get(tid)
            if not tmpl:
                return Response(status=404)

            await self.storage.templates.delete(tid)

            try:
                await self.engine.unload(tid)
            except KeyError as exc:
                log.debug(exc)

            return Response(tmpl)

    @resource('/workflow/templates/{tid}/{version:\d+}', version='v1')
    class TemplateVersion:

        async def get(self, request, tid, version):
            """
            Return the template's given version
            """
            tmpl = await self.storage.templates.get(tid, version, False)
            if not tmpl:
                return Response(status=404)

            return Response(tmpl)

        async def delete(self, request, tid, version):
            """
            Delete a template with given version
            """
            tmpl = await self.storage.templates.get(tid)
            if not tmpl:
                return Response(status=404)

            await self.storage.templates.delete(tid, version)
            return Response(tmpl[0])

    @resource('/workflow/templates/{tid}/draft', version='v1')
    class TemplateDraft:

        async def get(self, request, tid):
            """
            Return the template's draft, if any
            """
            tmpl = await self.storage.templates.get(tid, draft=True)
            if not tmpl:
                return Response(status=404)

            return Response(tmpl[0])

        async def post(self, request, tid):
            """
            Publish a draft into production
            """
            tmpl = await self.storage.templates.get(tid, draft=True)
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

            await self.engine.load(template)
            # Update draft into a new template
            await self.storage.templates.publish_draft(tid)
            return Response(draft)

        async def patch(self, request, tid):
            """
            Modify the template's draft
            """
            tmpl = await self.storage.templates.get(tid, draft=True)
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
                tmpl_dict = await self.api_new_draft(template)
            except ConflictError as exc:
                return Response(status=409, body={
                    'error': str(exc)
                })

            metadata = await self.storage.templates.get_metadata(template.uid)
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
            tmpl = await self.storage.templates.get(tid, draft=True)
            if not tmpl:
                return Response(status=404)

            await self.storage.templates.delete(tid, draft=True)
            return Response(tmpl[0])

    def serialize_wflow_exec(self, obj):
        """
        JSON default serializer for datetime/isoformat
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Workflow):
            return obj.report()
        raise TypeError('obj not serializable: {}'.format(obj))

    @resource('/workflow/instances', version='v1')
    class Workflows:

        async def get(self, request):
            """
            Return workflow instances
            """
            return Response(
                json.dumps(
                    [wflow for wflow in self.engine.instances.values()],
                    default=self.serialize_wflow_exec),
                content_type='application/json'
            )

        async def put(self, request):
            """
            Start a workflow from payload:
            {
                "id": "template_id",
                "draft": true/false
            }
            """
            request = await request.json()

            if 'id' not in request:
                return Response(status=400, body={
                    'error': "Template's ID key 'id' is mandatory"
                })

            draft = request.get('draft', False)
            templates = await self.storage.templates.get(
                request['id'],
                draft=draft,
                with_metadata=False
            )

            if not templates:
                return Response(status=404, body={
                    'error': 'Could not find a suitable template to run'
                })

            wf_tmpl = WorkflowTemplate.from_dict(templates[0])
            data = request.get('inputs', {})
            if draft:
                wflow = await self.engine.run_once(wf_tmpl, data)
            else:
                wflow = await self.engine.trigger(wf_tmpl.uid, data)

            if wflow is None:
                return Response(status=400, body={
                    'error': 'Could not start any workflow from this template'
                })
            return Response(
                json.dumps(wflow, default=self.serialize_wflow_exec),
                content_type='application/json'
            )

    @resource('/workflow/instances/{iid}', version='v1')
    class Workflow:

        async def get(self, request, iid):
            """
            Return a workflow instance
            """
            wflow = self.engine.instances.get(iid)
            if not wflow:
                return Response(status=404)

            return Response(
                json.dumps(wflow, default=self.serialize_wflow_exec),
                content_type='application/json'
            )

        async def post(self, request, iid):
            """
            Operate on a workflow instance
            """

    @resource('/workflow/tasks', version='v1')
    class Tasks:

        async def get(self, request):
            """
            Return the available tasks
            """
            return Response(self.AVAILABLE_TASKS)

    @resource('/workflow/topics', version='v1')
    class Topics:

        async def get(self, request):
            """
            Return the list of available topics
            """
            return Response(self.topics)

    @resource('/workflow/regexes', version='v1')
    class Regexes:

        async def get(self, request):
            """
            Return the list of all regexes
            """
            return Response(await self.storage.regexes.get_all())

        async def put(self, request):
            """
            Insert a new rule
            """
            request = await request.json()

            if 'name' not in request:
                return Response(status=400, body={
                    'error': "missing parameter 'name'"
                })

            data = {
                'id': str(uuid4()),
                'name': request['name'],
                'config': request.get('config', {})
            }

            await self.storage.regexes.insert(data)
            return Response(data)

        async def delete(self, request):
            """
            Delete all regexes and return the list
            """
            rules = await self.storage.regexes.get_all()
            await self.storage.regexes.delete()
            return Response(rules)

    @resource('/workflow/regexes/{rule_id}', version='v1')
    class Regex:

        async def get(self, request, rule_id):
            """
            Return the rule for id `rule_id`
            """
            rule = await self.storage.regexes.get(rule_id)
            if not rule:
                return Response(status=404)
            return Response(rule)

        async def patch(self, request, rule_id):
            """
            Modify an existing regex rule
            """
            rule = await self.storage.regexes.get(rule_id)
            if not rule:
                return Response(status=404)

            request = await request.json()

            data = {
                'id': rule_id,
                'name': request.get('name', rule['name']),
                'config': request.get('config', rule['config'])
            }

            await self.storage.regexes.insert(data)
            return Response(data)

        async def delete(self, request, rule_id):
            """
            Delete the rule with id `rule_id`
            """
            rule = await self.storage.regexes.get(rule_id)
            if not rule:
                return Response(status=F404)

            await self.storage.regexes.delete(rule_id=rule_id)
            return Response(rule)

    @resource('/workflow/lookups', version='v1')
    class Lookups:

        async def get(self, request):
            """
            Return the list of all lookups
            """
            return Response(await self.storage.lookups.get_all())

        async def put(self, request):
            """
            Insert a new rule
            """
            request = await request.json()

            if 'name' not in request:
                return Response(status=400, body={
                    'error': "missing parameter 'name'"
                })

            data = {
                'id': str(uuid4()),
                'name': request['name'],
                'config': request.get('config', {})
            }

            await self.storage.lookups.insert(data)
            return Response(data)

        async def delete(self, request):
            """
            Delete all lookups and return the list
            """
            rules = await self.storage.lookups.get_all()
            await self.storage.lookups.delete()
            return Response(rules)

    @resource('/workflow/lookups/{rule_id}', version='v1')
    class Lookup:

        async def get(self, request, rule_id):
            """
            Return the rule for id `rule_id`
            """
            rule = await self.storage.lookups.get(rule_id)
            if not rule:
                return Response(status=404)
            return Response(rule)

        async def patch(self, request, rule_id):
            """
            Modify an existing lookup rule
            """
            rule = await self.storage.lookups.get(rule_id)
            if not rule:
                return Response(status=404)

            request = await request.json()

            data = {
                'id': rule_id,
                'name': request.get('name', rule['name']),
                'config': request.get('config', rule['config'])
            }

            await self.storage.lookups.insert(data)
            return Response(data)

        async def delete(self, request, rule_id):
            """
            Delete the rule with id `rule_id`
            """
            rule = await self.storage.lookups.get(rule_id)
            if not rule:
                return Response(status=404)

            await self.storage.lookups.delete(rule_id=rule_id)
            return Response(rule)

    @resource('/test', version='v1')
    class Test:

        async def post(self, request):
            # Send data to all topics
            await self.TestTopic.post(self, request, None)

    @resource('/test/{topic}', version='v1')
    class TestTopic:

        async def post(self, request, topic):
            # Send data to the given topic
            await self.workflow_event(await request.json(), topic)
