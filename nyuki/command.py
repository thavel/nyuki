import os
import json
import logging
from argparse import ArgumentParser

from jsonschema import validate, ValidationError

from nyuki.log import DEFAULT_LOGGING


log = logging.getLogger(__name__)


CONF_FILE = 'conf.json'
CONF_SCHEMA = {
    "type": "object",
    "required": ["bus", "api", "log"],
    "properties": {
        "bus": {
            "type": "object",
            "required": ["jid", "password"],
            "properties": {
                "jid": {"type": "string"},
                "password": {"type": "string"}
            }
        }
    }
}


def _update_config(source, data, path):
    """
    Tool function to update nested dict values.
    It creates sub-dictionaries to eventually end up with the proper dest key.
    """
    if not data:
        return
    items = path.split('.')
    dest = items[-1]
    keys = items[:-1]
    last = source
    for k in keys:
        if not last.get(k):
            last[k] = dict()
        last = last[k]
    last[dest] = data

def _merge_config(defaults, updates):
    """
    Tool function to merge conf from defaults to the config file/command args.
    """
    conf = dict(defaults, **updates)
    for k in defaults.keys():
        if isinstance(defaults[k], dict) and k in updates:
            conf[k] = _merge_config(defaults[k], updates[k])
    return conf

def _build_args():
    """
    Build argument parser and actually parse them at runtime.
    """
    parser = ArgumentParser(description='Nyuki implementation')
    parser.add_argument('-d', '--debug',
                        help='debug mode',  action='store_true', required=False)
    parser.add_argument('-c', '--cfg',
                        help='config file', required=False, default=CONF_FILE)
    parser.add_argument('-j', '--jid',
                        help='xmpp jid: <user>[@<host>]', required=False)
    parser.add_argument('-p', '--pwd',
                        help='xmpp password', required=False)
    parser.add_argument('-s', '--srv',
                        help='xmpp server: <host>[:<port>]', required=False)
    parser.add_argument('-a', '--api',
                        help='api binding: <host>[:<port>]', required=False)
    return parser.parse_args()


def _read_file(path):
    """
    Load config from a JSON file.
    """
    if not os.path.isfile(path):
        log.error("File {} does not exist".format(path))
        exit(1)

    with open(path) as file:
        conf = json.loads(file.read())
    return conf


def parse_init():
    """
    Build, parse and merge configs into a unique dictionary that would be passed
    as nyuki default argument.
    """
    args = _build_args()
    conf = _read_file(args.cfg)

    # Updates for jid and password are straightforward
    _update_config(conf, args.jid, 'bus.jid')
    _update_config(conf, args.pwd, 'bus.password')

    # Add the bus port and host if needed
    if args.srv:
        try:
            host, port = args.srv.split(':')
            _update_config(conf, int(port), 'bus.port')
        except ValueError:
            host = args.srv
        _update_config(conf, host, 'bus.host')

    # Ensure the api section is always there, update if needed
    if args.api:
        try:
            host, port = args.api.split(':')
            _update_config(conf, int(port), 'api.port')
        except ValueError:
            host = args.api
        _update_config(conf, host, 'api.host')

    # Override root logger level for debug mode
    if args.debug:
        _update_config(conf, 'DEBUG', 'log.root.level')

    return conf

def exhaustive_config(updates):
    """
    Return an exhaustive version of configs based on the defaults and the
    initial values (both specified through the configuration file and the
    command arguments). Configs should be valid (based on a json schema).
    """
    defaults = {
        'bus': dict(),
        'api': dict(),
        'log': DEFAULT_LOGGING
    }
    conf = _merge_config(defaults, updates)

    try:
        validate(conf, CONF_SCHEMA)
    except ValidationError as error:
        log.error("Invalid configuration file: {}".format(error.message))
        exit(1)
    return conf
