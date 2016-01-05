import asyncio
import codecs
import json
from jsonschema import validate, ValidationError
import logging
import logging.config
from signal import SIGINT, SIGTERM
import sys

from nyuki.bus import Bus
from nyuki.capabilities import Exposer, Response, resource
from nyuki.commands import get_command_kwargs
from nyuki.config import (
    get_full_config, write_conf_json, merge_configs, DEFAULT_CONF_FILE
)
from nyuki.handlers import CapabilityHandler
from nyuki.service import ServiceManager


log = logging.getLogger(__name__)


class Nyuki(metaclass=CapabilityHandler):

    """
    A lightweigh base class to build nyukis. A nyuki provides tools that shall
    help the developer with managing the following topics:
      - Bus of communication between nyukis.
      - Asynchronous events.
      - Capabilities exposure through a REST API.
    This class has been written to perform the features above in a reliable,
    single-threaded, asynchronous and concurrent-safe environment.
    The core engine of a nyuki implementation is the asyncio event loop
    (a single loop is used for all features).
    A wrapper is also provide to ease the use of asynchronous calls
    over the actions nyukis are inteded to do.
    """

    # Configuration schema must follow jsonschema rules.
    BASE_CONF_SCHEMA = {
        "type": "object",
        "required": ["log"]
    }

    def __init__(self, **kwargs):
        # Set stdout as utf-8 codec
        try:
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
        except Exception as exc:
            # Nosetests seems to alter stdout, breaking detach()
            log.warning('Could not change stdout codec')
            log.exception(exc)

        # List of configuration schemas
        self._schemas = []

        # Get configuration from multiple sources and register base schema
        kwargs = kwargs or get_command_kwargs()
        self.config_filename = kwargs.get('config', DEFAULT_CONF_FILE)
        self._config = get_full_config(**kwargs)
        self.register_schema(self.BASE_CONF_SCHEMA)

        # Initialize logging
        logging.config.dictConfig(self._config['log'])

        self.loop = asyncio.get_event_loop() or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.services = ServiceManager(self)
        self.services.add('api', Exposer(self))
        if self._config.get('bus') is not None:
            self.services.add('bus', Bus(self))

        self.is_stopping = False

    def __getattribute__(self, name):
        """
        Getattr, or returns the specified service
        """
        try:
            return super().__getattribute__(name)
        except AttributeError as exc:
            try:
                return self.services.get(name)
            except KeyError:
                raise exc

    @property
    def config(self):
        return self._config

    def start(self):
        """
        Start the nyuki
        The nyuki process is terminated when this method is finished
        """
        self.loop.add_signal_handler(SIGTERM, self.abort, SIGTERM)
        self.loop.add_signal_handler(SIGINT, self.abort, SIGINT)

        # Configure services with nyuki's configuration
        log.debug('Running configure for services')
        for name, service in self.services.all.items():
            service.configure(**self._config.get(name, {}))
        log.debug('Done configuring')

        # Start services
        self.loop.run_until_complete(self.services.start())

        # Call for setup
        if not asyncio.iscoroutinefunction(self.setup):
            log.warning('setup method must be a coroutine')
            self.setup = asyncio.coroutine(self.setup)
        self.loop.run_until_complete(self.setup())

        # Main loop
        self.loop.run_forever()

        # Call for teardown
        if not asyncio.iscoroutinefunction(self.teardown):
            log.warning('teardown method must be a coroutine')
            self.teardown = asyncio.coroutine(self.teardown)
        self.loop.run_until_complete(self.teardown())

        # Close everything : terminates nyuki
        self.loop.close()

    def _stop_loop(self):
        """
        Call the loop to stop itself.
        """
        self.loop.call_soon_threadsafe(self.loop.stop)

    def abort(self, signal):
        """
        Signal handler: gracefully stop the nyuki.
        """
        log.warning('Caught signal %d, stopping nyuki', signal)
        asyncio.ensure_future(self.stop())

    async def stop(self, timeout=5):
        """
        Stop the nyuki
        """
        if self.is_stopping:
            log.warning('Force closing the nyuki')
            self._stop_loop()
            return

        self.is_stopping = True
        await self.services.stop()
        self._stop_loop()

    async def report_error(self, code, message):
        await self.bus.publish({
            'code': code,
            'message': message
        })

    def register_schema(self, schema, format_checker=None):
        """
        Add a jsonschema to validate on configuration update.
        """
        self._schemas.append((schema, format_checker))
        self._validate_config()

    def _validate_config(self, config=None):
        """
        Validate on all registered configuration schemas.
        """
        log.debug('Validating configuration')
        config = config or self._config
        for schema, checker in self._schemas:
            validate(config, schema, format_checker=checker)

    async def setup(self):
        """
        First thing called when starting the event loop, coroutine or not.
        """
        log.warning('Setup called, but not overridden')

    async def reload(self):
        """
        Called when the configuration is modified
        """
        log.warning('Reload called, but not overridden')

    async def teardown(self):
        """
        Called right before closing the event loop, stopping the Nyuki.
        """
        log.warning('Teardown called, but not overridden')

    def update_config(self, *new_confs):
        """
        Update the current configuration with the given list of dicts.
        """
        config = merge_configs(self._config, *new_confs)
        self._validate_config(config)
        self._config = config

    def save_config(self):
        """
        Save the current configuration dict to its JSON file.
        """
        write_conf_json(self.config, self.config_filename)

    async def _reload_config(self, request):
        """
        Reload the configuration and the services
        """
        self.save_config()
        logging.config.dictConfig(self._config['log'])
        await self.reload()
        for name, service in self.services.all.items():
            if name in request:
                await service.stop()
                service.configure(**self._config[name])
                asyncio.ensure_future(service.start())

    @resource(endpoint='/config', version='v1')
    class Configuration:

        def get(self, request):
            return Response(self._config)

        async def patch(self, request):
            try:
                self.update_config(request)
            except ValidationError as error:
                error = {'error': error.message}
                log.error('Bad configuration received : {}'.format(request))
                log.debug(error)
                return Response(body=error, status=400)

            # Reload what is necessary, return the http response immediately
            asyncio.ensure_future(self._reload_config(request))

            return Response(self._config)

    @resource(endpoint='/swagger', version='v1')
    class Swagger:

        def get(self, request):
            try:
                with open('swagger.json', 'r') as f:
                    body = json.loads(f.read())
            except OSError:
                return Response(status=404, body={
                    'error': 'Missing swagger documentation'
                })

            return Response(body=body)
