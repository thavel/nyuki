import signal
import threading
import logging
import logging.config

from nyuki.logging import DEFAULT_LOGGING
from nyuki.loop import EventLoop
from nyuki.bus import Bus


log = logging.getLogger(__name__)


class Nyuki(object):

    def __init__(self):
        # Let's assume we've fetch configs through the command line / conf file
        self.config = {
            'bus': {
                'jid': 'test@localhost',
                'password': 'test',
                'host': '192.168.0.216'
            }
        }

        logging.config.dictConfig(DEFAULT_LOGGING)
        self._capabilities = dict()
        self._bus = Bus(**self.config['bus'])
        self._loop = EventLoop(loop=self._bus.loop)

    @property
    def event_loop(self):
        return self._loop

    @property
    def capabilities(self):
        return self._capabilities

    def start(self):
        signal.signal(signal.SIGTERM, self.abort)
        signal.signal(signal.SIGINT, self.abort)
        self._bus.connect(block=False)

    def abort(self, signum=signal.SIGINT, frame=None):
        log.warning("Caught signal {}".format(signum))
        self.stop()

    def stop(self, timeout=5):
        self._bus.disconnect(timeout=timeout)
        log.info("Nyuki exiting")
