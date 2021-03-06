import asyncio
import logging
import re
from enum import Enum
from uuid import uuid4
from datetime import datetime
from aiohttp.web import FileField
from tukio import get_broker, EXEC_TOPIC
from tukio.utils import FutureState
from tukio.workflow import WorkflowTemplate, WorkflowExecState
from pymongo import DESCENDING, ASCENDING
from pymongo.errors import AutoReconnect, DuplicateKeyError

from nyuki.utils import from_isoformat
from nyuki.api import Response, resource, content_type
from nyuki.workflow.tasks.utils.uri import URI, InvalidWorkflowUri


log = logging.getLogger(__name__)


class Ordering(Enum):

    title_asc = ('title', ASCENDING)
    title_desc = ('title', DESCENDING)
    start_asc = ('exec.start', ASCENDING)
    start_desc = ('exec.start', DESCENDING)
    end_asc = ('exec.end', ASCENDING)
    end_desc = ('exec.end', DESCENDING)

    @classmethod
    def keys(cls):
        return [key for key in cls.__members__.keys()]


class InstanceCollection:

    REQUESTER_REGEX = re.compile(r'^nyuki://.*')

    def __init__(self, instances_collection):
        self._instances = instances_collection
        asyncio.ensure_future(self._instances.create_index('exec.id', unique=True))
        asyncio.ensure_future(self._instances.create_index('exec.state'))
        asyncio.ensure_future(self._instances.create_index('exec.requester'))
        # Search and sorting indexes
        asyncio.ensure_future(self._instances.create_index('title'))
        asyncio.ensure_future(self._instances.create_index('exec.start'))
        asyncio.ensure_future(self._instances.create_index('exec.end'))

    async def get_one(self, exec_id):
        """
        Return the instance with `exec_id` from workflow history.
        """
        return await self._instances.find_one({'exec.id': exec_id}, {'_id': 0})

    async def get(self, root=False, full=False, offset=None, limit=None,
                  since=None, state=None, search=None, order=None):
        """
        Return all instances from history from `since` with state `state`.
        """
        query = {}
        # Prepare query
        if isinstance(since, datetime):
            query['exec.start'] = {'$gte': since}
        if isinstance(state, Enum):
            query['exec.state'] = state.value
        if root is True:
            query['exec.requester'] = {'$not': self.REQUESTER_REGEX}
        if search:
            query['title'] = {'$regex': '.*{}.*'.format(search)}

        if full is False:
            fields = {
                '_id': 0,
                'title': 1,
                'exec': 1,
                'id': 1,
                'version': 1,
                'draft': 1
            }
        else:
            fields = {'_id': 0}

        cursor = self._instances.find(query, fields)
        # Count total results regardless of limit/offset
        count = await cursor.count()

        # Sort depending on Order enum values
        if order is not None:
            cursor.sort(*order)
        else:
            # End descending by default
            cursor.sort(*Ordering.end_desc.value)

        # Set offset and limit
        if isinstance(offset, int) and offset >= 0:
            cursor.skip(offset)
        if isinstance(limit, int) and limit > 0:
            cursor.limit(limit)

        # Execute query
        return count, await cursor.to_list(None)

    async def insert(self, workflow):
        """
        Insert a finished workflow report into the workflow history.
        """
        try:
            await self._instances.insert(workflow)
        except DuplicateKeyError:
            # If it's a duplicate, we don't want to lose it
            workflow['exec']['duplicate'] = workflow['exec']['id']
            workflow['exec']['id'] = str(uuid4())
            await self._instances.insert(workflow)


class _WorkflowResource:

    """
    Share methods between workflow resources
    """

    def register_async_handler(self, async_topic, wflow):
        broker = get_broker()

        async def exec_handler(event):
            # Pass if event does not concern this workflow execution
            if event.source._workflow_exec_id != wflow.uid:
                return
            # Publish the event's data
            # TODO: Beware of unserializable objects
            asyncio.ensure_future(self.nyuki.bus.publish(
                event.data, topic=async_topic
            ))
            # If the workflow is in a final state, unregister
            if event.data['type'] in [
                WorkflowExecState.end.value,
                WorkflowExecState.error.value
            ]:
                broker.unregister(exec_handler, topic=EXEC_TOPIC)

        broker.register(exec_handler, topic=EXEC_TOPIC)


@resource('/workflow/instances', ['v1'], 'application/json')
class ApiWorkflows(_WorkflowResource):

    async def get(self, request):
        """
        Return workflow instances
        """
        return Response([
            workflow.report()
            for workflow in self.nyuki.running_workflows.values()
        ])

    async def put(self, request):
        """
        Start a workflow from payload:
        {
            "id": "template_id",
            "draft": true/false
            "exec": {}
        }
        """
        async_topic = request.headers.get('X-Surycat-Async-Topic')
        exec_track = request.headers.get('X-Surycat-Exec-Track')
        requester = request.headers.get('Referer')
        request = await request.json()

        if 'id' not in request:
            return Response(status=400, body={
                'error': "Template's ID key 'id' is mandatory"
            })
        draft = request.get('draft', False)
        data = request.get('inputs', {})
        exec = request.get('exec')

        if exec:
            # Suspended/crashed instance
            # The request's payload is the last known execution report
            templates = [request]
            if exec['id'] in self.nyuki.running_workflows:
                return Response(status=400, body={
                    'error': 'This workflow is already being rescued'
                })
        else:
            # Fetch the template from the storage
            try:
                templates = await self.nyuki.storage.templates.get(
                    request['id'],
                    draft=draft,
                    with_metadata=True
                )
            except AutoReconnect:
                return Response(status=503)

        if not templates:
            return Response(status=404, body={
                'error': 'Could not find a suitable template to run'
            })

        wf_tmpl = WorkflowTemplate.from_dict(templates[0])
        if exec:
            wflow = await self.nyuki.engine.rescue(wf_tmpl, request)
        elif draft:
            wflow = await self.nyuki.engine.run_once(wf_tmpl, data)
        else:
            wflow = await self.nyuki.engine.trigger(wf_tmpl.uid, data)

        if wflow is None:
            return Response(status=400, body={
                'error': 'Could not start any workflow from this template'
            })

        # Prevent workflow loop
        exec_track = exec_track.split(',') if exec_track else []
        holder = self.nyuki.bus.name
        for ancestor in exec_track:
            try:
                info = URI.parse(ancestor)
            except InvalidWorkflowUri:
                continue
            if info.template_id == wf_tmpl.uid and info.holder == holder:
                return Response(status=400, body={
                    'error': 'Loop detected between workflows'
                })

        # Keep full instance+template in nyuki's memory
        wfinst = self.nyuki.new_workflow(
            templates[0], wflow,
            track=exec_track,
            requester=requester
        )
        # Handle async workflow exec updates
        if async_topic is not None:
            self.register_async_handler(async_topic, wflow)

        return Response(wfinst.report())


@resource('/workflow/instances/{iid}', versions=['v1'])
class ApiWorkflow(_WorkflowResource):

    async def get(self, request, iid):
        """
        Return a workflow instance
        """
        try:
            return Response(self.nyuki.running_workflows[iid].report())
        except KeyError:
            return Response(status=404)

    async def post(self, request, iid):
        """
        Suspend/resume a runnning workflow.
        """
        try:
            wf = self.nyuki.running_workflows[iid]
        except KeyError:
            return Response(status=404)

        request = await request.json()

        try:
            action = request['action']
        except KeyError:
            return Response(status=400, body={
                'action parameter required'
            })

        # Should we return 409 Conflict if the status is already set ?
        if action == 'suspend':
            wf.instance.suspend()
        elif action == 'resume':
            wf.instance.resume()
        else:
            return Response(status=400, body={
                "action must be 'suspend' or 'resume'"
            })

        return Response(wf.report())

    async def delete(self, request, iid):
        """
        Cancel a workflow instance.
        """
        try:
            self.nyuki.running_workflows[iid].instance.cancel()
        except KeyError:
            return Response(status=404)


@resource('/workflow/history', versions=['v1'])
class ApiWorkflowsHistory:

    async def get(self, request):
        """
        Filters:
            * `root` return only the root workflows
            * `full` return the full graph and details of all workflows
                * :warning: can be a huge amount of data
            * `since` return the workflows since this date
            * `state` return the workflows on this FutureState
            * `offset` return the worflows from this offset
            * `limit` return this amount of workflows
            * `order` order results following the Ordering enum values
            * `search` search templates with specific title
        """
        # Filter on start date
        since = request.GET.get('since')
        if since:
            try:
                since = from_isoformat(since)
            except ValueError:
                return Response(status=400, body={
                    'error': "Could not parse date '{}'".format(since)
                })
        # Filter on state value
        state = request.GET.get('state')
        if state:
            try:
                state = FutureState(state)
            except ValueError:
                return Response(status=400, body={
                    'error': "Unknown state '{}'".format(state)
                })
        # Skip first items
        offset = request.GET.get('offset')
        if offset:
            try:
                offset = int(offset)
            except ValueError:
                return Response(status=400, body={
                    'error': 'Offset must be an int'
                })
        # Limit max result
        limit = request.GET.get('limit')
        if limit:
            try:
                limit = int(limit)
            except ValueError:
                return Response(status=400, body={
                    'error': 'Limit must be an int'
                })
        order = request.GET.get('ordering')
        if order:
            try:
                order = Ordering[order].value
            except KeyError:
                return Response(status=400, body={
                    'error': 'Ordering must be in {}'.format(Ordering.keys())
                })

        try:
            count, history = await self.nyuki.storage.instances.get(
                root=(request.GET.get('root') == '1'),
                full=(request.GET.get('full') == '1'),
                search=request.GET.get('search'),
                order=order,
                offset=offset, limit=limit, since=since, state=state,
            )
        except AutoReconnect:
            return Response(status=503)

        data = {'count': count, 'data': history}
        return Response(data)


@resource('/workflow/history/{uid}', versions=['v1'])
class ApiWorkflowHistory:

    async def get(self, request, uid):
        try:
            workflow = await self.nyuki.storage.instances.get_one(uid)
        except AutoReconnect:
            return Response(status=503)
        if not workflow:
            return Response(status=404)
        return Response(workflow)


@resource('/workflow/triggers', versions=['v1'])
class ApiWorkflowTriggers:

    async def get(self, request):
        """
        Return the list of all trigger forms
        """
        try:
            triggers = await self.nyuki.storage.triggers.get_all()
        except AutoReconnect:
            return Response(status=503)
        return Response(triggers)

    @content_type('multipart/form-data')
    async def put(self, request):
        """
        Upload a trigger form file
        """
        data = await request.post()
        try:
            form = data['form']
            tid = data['tid']
        except KeyError:
            return Response(status=400, body={
                'error': "'form' and 'tid' are mandatory parameters"
            })
        if not isinstance(form, FileField):
            return Response(status=400, body={
                'error': "'form' field must be a file content"
            })

        content = form.file.read().decode('utf-8')
        try:
            tmpl = await self.nyuki.storage.templates.get(tid)
            if not tmpl:
                return Response(status=404)
            trigger = await self.nyuki.storage.triggers.insert(tid, content)
        except AutoReconnect:
            return Response(status=503)
        return Response(trigger)


@resource('/workflow/triggers/{tid}', versions=['v1'])
class ApiWorkflowTrigger:

    async def get(self, request, tid):
        """
        Return a single trigger form
        """
        try:
            trigger = await self.nyuki.storage.triggers.get(tid)
        except AutoReconnect:
            return Response(status=503)
        if not trigger:
            return Response(status=404)
        return Response(trigger)

    async def delete(self, request, tid):
        """
        Delete a trigger form
        """
        try:
            trigger = await self.nyuki.storage.triggers.get(tid)
        except AutoReconnect:
            return Response(status=503)
        if not trigger:
            return Response(status=404)

        await self.nyuki.storage.triggers.delete(tid)
        return Response(trigger)
