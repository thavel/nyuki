import logging
from argparse import ArgumentParser


log = logging.getLogger(__name__)


def _build_args():
    """
    Build argument parser and actually parse them at runtime.
    """
    parser = ArgumentParser(description='Nyuki implementation')
    parser.add_argument('-l', '--logging',
                        help='debug mode', required=False, default='INFO',
                        choices=[
                            'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
                        ])
    parser.add_argument('-c', '--config',
                        help='config file name', required=False)
    parser.add_argument('-j', '--jid',
                        help='xmpp jid: <user>[@<host>]', required=False)
    parser.add_argument('-p', '--password',
                        help='xmpp password', required=False)
    parser.add_argument('-s', '--server',
                        help='xmpp server: <host>[:<port>]', required=False)
    parser.add_argument('-a', '--api',
                        help='api binding: <host>[:<port>]', required=False)
    return parser.parse_args()


def get_command_kwargs():
    args = _build_args()
    available = ['logging', 'config', 'jid', 'password', 'server', 'api']

    return {
        arg: getattr(args, arg)
        for arg
        in available
        if getattr(args, arg) is not None
    }
