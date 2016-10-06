from aiohttp import ClientSession
import asyncio
import json
import logging
from uuid import uuid4

from tukio.task import register
from tukio.task.holder import TaskHolder
from tukio.workflow import WorkflowExecState, Workflow

from .utils import runtime


log = logging.getLogger(__name__)


@register('trigger_workflow', 'execute')
class TriggerWorkflowTask(TaskHolder):

    WORKFLOW_URL = 'http://{host}{nyuki_api}/v1/workflow/instances'
    SCHEMA = {
        'type': 'object',
        'required': ['nyuki_api', 'template'],
        'properties': {
            'nyuki_api': {'type': 'string', 'description': 'nyuki_api'},
            'template': {'type': 'string', 'description': 'template_id'},
            'draft': {'type': 'boolean'},
            'await_completion': {'type': 'boolean'},
            'timeout': {'type': 'integer', 'minimum': 1, 'default': 60}
        },
        'dependencies': {
            'await_completion': ['timeout']
        },
        'additionalProperties': False
    }

    def __init__(self, config):
        super().__init__(config)
        self.template = self.config['template']
        self.draft = self.config.get('draft', False)
        self.blocking = self.config.get('await_completion', False)
        self.recipient_field = self.config.get('recipient_field', 'recipient')
        self.timeout = self.config.get('timeout', 60)
        # Workflow URL
        self.nyuki_api = self.config.get('nyuki_api') or ''
        if self.nyuki_api and not self.nyuki_api.startswith('/'):
            self.nyuki_api = '/' + self.nyuki_api
        self.url = self.WORKFLOW_URL.format(
            host=runtime.config.get('http_host', 'localhost'),
            nyuki_api=self.nyuki_api
        )

    async def async_exec(self, topic, data):
        log.debug(
            "Received data for async trigger_workflow in '%s': %s", topic, data
        )
        if data['type'] in [WorkflowExecState.end.value, WorkflowExecState.error.value]:
            self.async_future.set_result(data)
            asyncio.ensure_future(runtime.bus.unsubscribe(topic))

    async def execute(self, event):
        """
        Entrypoint execution method.
        """
        data = event.data

        # Send the HTTP request
        log.info('Request %s to process template %s', self.nyuki_api, self.template)
        log.debug(
            'Request details: url=%s, draft=%s, data=%s',
            self.url, self.draft, data
        )

        # Handle blocking trigger_workflow using mqtt
        workflow = Workflow.current_workflow()
        headers = {
            'Content-Type': 'application/json',
            'Referer': '{}/{}'.format(runtime.bus.name, workflow.uid)
        }

        if self.blocking:
            topic = '{}/async/{}'.format(runtime.bus.name, str(uuid4())[:8])
            headers['X-Surycat-Async-Topic'] = topic
            self.async_future = asyncio.Future()
            await runtime.bus.subscribe(topic, self.async_exec)
            asyncio.get_event_loop().call_later(
                self.timeout,
                asyncio.ensure_future,
                runtime.bus.unsubscribe(topic)
            )

        async with ClientSession() as session:
            params = {
                'url': self.url,
                'headers': headers,
                'data': json.dumps({
                    'id': self.template,
                    'draft': self.draft,
                    'inputs': data
                })
            }
            async with session.put(**params) as response:
                # Response validity
                if response.status != 200:
                    raise RuntimeError(
                        "Can't process remote workflow template {} on {}".format(
                            self.template, self.nyuki_api
                        )
                    )
                resp_body = await response.json()

        log.debug('Request sent successfully to {}', self.nyuki_api)

        # Block until task completed
        if self.blocking:
            instance = resp_body['exec']['id']
            log.info('Waiting for %s@%s to complete', instance, self.nyuki_api)
            await asyncio.wait_for(self.async_future, self.timeout)
            log.info('Instance %s@%s is done', instance, self.nyuki_api)

        return data
