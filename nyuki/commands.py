import os
import json
import logging
from argparse import ArgumentParser

from jsonschema import validate, ValidationError

from nyuki.logs import DEFAULT_LOGGING


log = logging.getLogger(__name__)

# Configuration schema must follow jsonschema rules.
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

# Nyuki default config file
DEFAULT_CONF_FILE = 'conf.json'

# Basic configuration for all Nyukis.
BASE_CONF = {
    'bus': dict(),
    'api': dict(),
    'log': DEFAULT_LOGGING
}


def update_config(source, data, path):
    """
    Tool function to update nested dict values.
    It creates sub-dictionaries to eventually end up with the proper dest key.
    """
    items = path.split('.')
    dest = items[-1]
    keys = items[:-1]
    last = source
    for k in keys:
        last = last.setdefault(k, {})
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


def build_args():
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
                        help='config file name', required=False,
                        default=DEFAULT_CONF_FILE)
    parser.add_argument('-j', '--jid',
                        help='xmpp jid: <user>[@<host>]', required=False)
    parser.add_argument('-p', '--password',
                        help='xmpp password', required=False)
    parser.add_argument('-s', '--server',
                        help='xmpp server: <host>[:<port>]', required=False)
    parser.add_argument('-a', '--api',
                        help='api binding: <host>[:<port>]', required=False)
    return parser.parse_args()


def _read_file(path):
    """
    Load config from a JSON file.
    """
    if not os.path.isfile(path):
        log.error("File {path} does not exist".format(path=path))
        exit(1)

    with open(path) as file:
        return json.loads(file.read())


def _exhaustive_config(updates):
    """
    Return an exhaustive version of configs based on the defaults and the
    initial values (both specified through the configuration file and the
    command arguments). Configs should be valid (based on a json schema).
    """
    conf = _merge_config(BASE_CONF, updates)

    try:
        validate(conf, CONF_SCHEMA)
    except ValidationError as error:
        log.error("Invalid configuration: {}".format(error.message))
        exit(1)
    return conf


def read_conf_json(filename, args):
    """
    Build, parse and merge configs into a unique dictionary
    that would be passed as nyuki default argument.
    """
    conf = _read_file(filename)

    # Updates for jid and password are straightforward
    if args.jid is not None:
        update_config(conf, args.jid, 'bus.jid')
    if args.password is not None:
        update_config(conf, args.password, 'bus.password')

    # Add the bus port and host if needed
    if args.server:
        try:
            host, port = args.server.split(':')
            update_config(conf, int(port), 'bus.port')
        except ValueError:
            host = args.server
        update_config(conf, host, 'bus.host')

    # Ensure the api section is always there, update if needed
    if args.api:
        try:
            host, port = args.api.split(':')
            update_config(conf, int(port), 'api.port')
        except ValueError:
            host = args.api
        update_config(conf, host, 'api.host')

    # Override root logger level
    update_config(conf, args.logging, 'log.root.level')

    return _exhaustive_config(conf)


def write_conf_json(config, filename):
    """
    Save the given configuration to a file in json format.
    """
    with open(filename, 'w') as jsonfile:
        json.dump(config, jsonfile)
