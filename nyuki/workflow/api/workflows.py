import asyncio
from datetime import datetime
import json
from tukio import get_broker, EXEC_TOPIC
from tukio.workflow import (
    Workflow, WorkflowTemplate, WorkflowExecState
)

from nyuki.api import Response, resource


class _WorkflowResource:

    """
    Share methods between workflow resources
    """

    def serialize_wflow_exec(self, obj):
        """
        JSON default serializer for datetime/isoformat
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Workflow):
            return obj.report()
        raise TypeError('obj not serializable: {}'.format(obj))

    def register_async_handler(self, async_channel, wflow):
        broker = get_broker()
        async def exec_handler(event):
            # Pass if event does not concern this workflow execution
            if event.source.workflow_exec_id != wflow.uid:
                return
            # Publish the event's data
            # TODO: Beware of unserializable objects
            asyncio.ensure_future(self.nyuki.bus.publish(
                event.data, topic=async_channel
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
                [wflow for wflow in self.nyuki.engine.instances.values()],
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
        async_channel = request.headers.get('X-Surycat-Async-Channel')
        request = await request.json()

        if 'id' not in request:
            return Response(status=400, body={
                'error': "Template's ID key 'id' is mandatory"
            })

        draft = request.get('draft', False)
        templates = await self.nyuki.storage.templates.get(
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
            wflow = await self.nyuki.engine.run_once(wf_tmpl, data)
        else:
            wflow = await self.nyuki.engine.trigger(wf_tmpl.uid, data)

        if wflow is None:
            return Response(status=400, body={
                'error': 'Could not start any workflow from this template'
            })

        # Handle async workflow exec updates
        if async_channel is not None:
            self.register_async_handler(async_channel, wflow)

        return Response(
            json.dumps(wflow, default=self.serialize_wflow_exec),
            content_type='application/json'
        )


@resource('/workflow/instances/{iid}', versions=['v1'])
class ApiWorkflow(_WorkflowResource):

    async def get(self, request, iid):
        """
        Return a workflow instance
        """
        wflow = self.nyuki.engine.instances.get(iid)
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


@resource('/test', versions=['v1'])
class ApiTest:

    async def post(self, request):
        # Send data to all topics
        await ApiTestTopic.post(self, request, None)


@resource('/test/{topic}', versions=['v1'])
class ApiTestTopic:

    async def post(self, request, topic):
        # Send data to the given topic
        await self.nyuki.workflow_event(topic, await request.json())
