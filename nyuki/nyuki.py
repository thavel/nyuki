import logging
import signal
import threading

from nyuki.messaging.event import Event, EventManager
from nyuki.messaging.nbus import Nbus


log = logging.getLogger(__name__)


class Terminate(Event):
    pass


class Nyuki(object):
    """A lightweight base class for creating nyukies. This mainly provides
    tools that shall help the developer with managing the following topics:
      - threading
      - bus
    """

    GOODBYE_ANNOUNCE = "goodbye"

    def __init__(self, **kwargs):
        """
        A nyuki instance is passed all the command-line arguments of the
        sub-command 'start'.
        """
        # The attribute `config` is meant to store all the parameters from the
        # command-line and the config file.
        self.config = {}
        # Init event stack
        self._event_stack = EventManager(self)
        # Init bus layer
        # config should contains xmpp credentials in the form:
        # {'jid': nyuki_jid, 'password': nyuki_password}
        xmpp = self.config['xmpp']
        self.bus = Nbus(
            xmpp['jid'],
            xmpp['password'],
            event_stack=self._event_stack
        )

    def start(self):
        """
        Start the nuyki and all its threads
        """

    def run(self):
        """
        Start a nyuki as a standalone process
        """
        signal.signal(signal.SIGTERM, self._kill)
        signal.signal(signal.SIGINT, self._kill)
        self.bus.connect()

    def _kill(self, signum, frame):
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

        def goodbye(iq, sessions):
            self.fire(Terminate())
            self.bus.disconnect()
            try:
                threads = threading.enumerate().remove(
                    threading.main_thread()
                ) or []
            except ValueError:
                pass
            for t in threads:
                t.join()
        self.send_goodbye(success_callback=goodbye,
                          error_callback=goodbye)

    def _send_bus_unicast(self, message):
        '''
            The message argument should be an instance of
            sleekxmpp.stanza.Message
        '''
        self.bus.send_unicast(message)

    def _send_bus_broadcast(self, message):
        '''
            This method use the announce behaviours that is described in
            the xep 0133. See the nbus method for detail.
        '''
        self.bus.send_broadcast(message)

    def send_goodbye(self):
        '''
        Send a message on the bus announcing the termination of the Nyuki
        '''
        message = self.GOODBYE_ANNOUNCE
        self.send_broadcast(message)

    def send_bus_message(self, message):
        '''
        Method that enable to send a message on the bus
        Can call _send_bus_unicast and _send_bus_broadcast methods
        '''
        pass

    def handle_bus_message(self, message):
        '''
        method called when a message is received from the bus
        '''
        pass
