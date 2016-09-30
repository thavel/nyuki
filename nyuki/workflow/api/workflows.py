import asyncio
from datetime import datetime
import json
import logging
from pymongo.errors import AutoReconnect
from aiohttp.web_reqrep import FileField
from tukio import get_broker, EXEC_TOPIC
from tukio.utils import FutureState
from tukio.workflow import (
    Workflow, WorkflowTemplate, WorkflowExecState
)

from nyuki.api import Response, resource, content_type
from nyuki.utils import from_isoformat


log = logging.getLogger(__name__)


def serialize_wflow_exec(obj):
    """
    JSON default serializer for workflows and datetime/isoformat.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Workflow):
        return obj.report()
    return 'Internal server data: {}'.format(type(obj))


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
        return Response(
            json.dumps(
                [workflow.report()
                 for workflow in self.nyuki.running_workflows.values()],
                default=serialize_wflow_exec
            ),
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
        async_topic = request.headers.get('X-Surycat-Async-Topic')
        requester = request.headers.get('Referer')
        request = await request.json()

        if 'id' not in request:
            return Response(status=400, body={
                'error': "Template's ID key 'id' is mandatory"
            })

        draft = request.get('draft', False)
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
        data = request.get('inputs', {})
        if draft:
            wflow = await self.nyuki.engine.run_once(wf_tmpl, data)
        else:
            wflow = await self.nyuki.engine.trigger(wf_tmpl.uid, data)

        if wflow is None:
            return Response(status=400, body={
                'error': 'Could not start any workflow from this template'
            })

        # Keep full instance+template in nyuki's memory
        wfinst = self.nyuki.new_workflow(templates[0], wflow, requester)
        # Handle async workflow exec updates
        if async_topic is not None:
            self.register_async_handler(async_topic, wflow)

        return Response(
            json.dumps(
                wfinst.report(),
                default=serialize_wflow_exec
            ),
            content_type='application/json'
        )


@resource('/workflow/instances/{iid}', versions=['v1'])
class ApiWorkflow(_WorkflowResource):

    async def get(self, request, iid):
        """
        Return a workflow instance
        """
        try:
            return Response(
                json.dumps(
                    self.nyuki.running_workflows[iid].report(),
                    default=serialize_wflow_exec
                ),
                content_type='application/json'
            )
        except KeyError:
            return Response(status=404)

    async def delete(self, request, iid):
        """
        Cancel a workflow instance.
        """
        for instance in self.nyuki.engine.instances:
            if instance.uid == iid:
                instance.cancel()
                return

        return Response(status=404)


@resource('/workflow/history', versions=['v1'])
class ApiWorkflowsHistory:

    async def get(self, request):
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
        try:
            history = await self.nyuki.storage.instances.get(
                offset=offset, limit=limit, since=since, state=state
            )
        except AutoReconnect:
            return Response(status=503)
        return Response(
            json.dumps(history, default=serialize_wflow_exec),
            content_type='application/json'
        )


@resource('/workflow/history/{uid}', versions=['v1'])
class ApiWorkflowHistory:

    async def get(self, request, uid):
        try:
            workflow = await self.nyuki.storage.instances.get_one(uid)
        except AutoReconnect:
            return Response(status=503)
        if not workflow:
            return Response(status=404)
        return Response(
            json.dumps(workflow, default=serialize_wflow_exec),
            content_type='application/json'
        )


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
