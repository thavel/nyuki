import os
import json
import logging

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


def read_conf_json(path):
    """
    Load config from a JSON file.
    """
    if not os.path.isfile(path):
        log.error("File {path} does not exist".format(path=path))
        raise Exception("Invalid configuration path: %s" % path)

    with open(path) as file:
        return json.loads(file.read())


def get_full_config(**kwargs):
    """
    Return an exhaustive version of configs based on the defaults and the
    initial values (both specified through the configuration file and the
    command arguments). Configs should be valid (based on a json schema).
    """
    conf = BASE_CONF

    # We load the conf json if any
    if 'config' in kwargs:
        file_config = read_conf_json(kwargs['config'])
        conf = _merge_config(conf, file_config)

    # Updates for jid and password are straightforward
    if 'jid' in kwargs:
        update_config(conf, kwargs['jid'], 'bus.jid')
    if 'password' in kwargs:
        update_config(conf, kwargs['password'], 'bus.password')

    # Add the bus port and host if needed
    if 'server' in kwargs:
        try:
            host, port = kwargs['server'].split(':')
            update_config(conf, int(port), 'bus.port')
        except ValueError:
            host = kwargs['server']
        update_config(conf, host, 'bus.host')

    # Ensure the api section is always there, update if needed
    if 'api' in kwargs:
        try:
            host, port = kwargs['api'].split(':')
            update_config(conf, int(port), 'api.port')
        except ValueError:
            host = kwargs['api']
        update_config(conf, host, 'api.host')

    # Override root logger level
    if 'logging' in kwargs:
        update_config(conf, kwargs['logging'], 'log.root.level')

    try:
        validate(conf, CONF_SCHEMA)
    except ValidationError as error:
        log.error("Invalid configuration: {}".format(error.message))
        raise

    return conf


def write_conf_json(config, filename):
    """
    Save the given configuration to a file in json format.
    """
    with open(filename, 'w') as jsonfile:
        json.dump(config, jsonfile)
