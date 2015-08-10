import logging
import logging.config
import signal
import threading

from nyuki.messaging.event import EventManager, on_event, Terminate
from nyuki.messaging.nbus import Nbus, SessionStart


log = logging.getLogger()


DEFAULT_LOGGING = {
    "version": 1,
    "formatters": {
        "long": {
            "format": "%(asctime)-24s %(levelname)-8s [%(processName)-12s] [%(name)s] %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "long",
            "stream": "ext://sys.stdout"
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG"
    },
    "loggers": {
        "sleekxmpp": {
            "level": "INFO"
        }
    },
    "disable_existing_loggers": False
}


class Nyuki(object):

    """A lightweight base class for creating nyukies. This mainly provides
    tools that shall help the developer with managing the following topics:
      - threading
      - bus
    """

    def __init__(self, **kwargs):
        """
        A nyuki instance is passed all the command-line arguments of the
        sub-command 'start'.
        """
        logging.config.dictConfig(DEFAULT_LOGGING)
        self._stopping = threading.Event()
        # The attribute `config` is meant to store all the parameters from the
        # command-line and the config file.
        self.config = {
            'xmpp': {
                'jid': 'dummy@localhost',
                'password': 'dummy'
            }
        }
        # Init bus layer
        self._event_stack = EventManager(self)
        # config should contains xmpp credentials in the form:
        # {'jid': nyuki_jid, 'password': nyuki_password}
        xmpp = self.config['xmpp']
        self.bus = Nbus(xmpp['jid'], xmpp['password'], self._event_stack)

    @on_event(SessionStart)
    def start(self, _):
        """
        Start the nuyki and all its threads
        """
        log.info('Connected! woo!')

    def run(self):
        """
        Start a nyuki as a standalone process
        """
        signal.signal(signal.SIGTERM, self._kill)
        signal.signal(signal.SIGINT, self._kill)
        self.bus.connect()

    def _kill(self, signum, _):
        """
        Stop the nuyki and all its threads in a graceful fashion
        """
        signals = {
            getattr(signal, s): s for s in dir(signal)
            if s.startswith('SIG') and not s.startswith('SIG_')
        }
        log.warning("caught signal {}".format(signals[signum]))
        if not self._stopping.is_set():
            self.stop()

    def stop(self):
        """
        Disconnect from the bus and eventually call custom handlers (that catch
        the `Terminate` event) to properly cleanup things before exiting.
        """
        self._stopping.set()
        self.bus.disconnect()
        self.fire(Terminate())
        threads = threading.enumerate().remove(threading.main_thread()) or []
        for t in threads:
            t.join()

    def _send_bus_unicast(self, message):
        '''
            The message argument should be an instance of
            sleekxmpp.stanza.Message
        '''
        self.bus.send_unicast(message)

    def send_bus_message(self, message):
        '''
        Method that enable to send a message on the bus
        Can call _send_bus_unicast and _send_bus_broadcast methods
        '''
        self.bus.send_unicast(message)

    def handle_bus_message(self, message):
        '''
        method called when a message is received from the bus
        '''
        pass
