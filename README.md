# Nyuki :bee:

[![Circle CI](https://img.shields.io/circleci/project/optiflows/nyuki/master.svg)](https://circleci.com/gh/optiflows/nyuki)
[![pypi version](http://img.shields.io/pypi/v/nyuki.svg)](https://pypi.python.org/pypi/nyuki)
[![python versions](https://img.shields.io/pypi/pyversions/nyuki.svg)](https://pypi.python.org/pypi/nyuki/)


## tl;dr
A lightweight Python library designed to implement agents (aka nyukis). It provides features that shall help developers with managing the following topics:

* Expose service features through a RESTful API
* Communication between nyukis (over HTTP, XMPP or MQTT)
* Helpers for asyncio-based programming

This library has been written with a focus on reliability and developer-friendliness. Its design promotes single-threaded and asynchronous coding style through the extensive use of the [Python asyncio](https://docs.python.org/3/library/asyncio.html) event loop. A single loop is used to manage HTTP, XMPP-based and MQTT-based communications as well as executing internal logic. Nyukis are suited for Agent-Oriented Programming and very useful to build distributed systems and scalable services.

## What is a nyuki?
A nyuki (a bee in Swahili) is an entity designed for real-time data processing (stream processing). Tying together several nyukis allows nearly unlimited use cases: from home automation (e.g. warm up my home when you're less than 5 miles away) to smart industries (lower down pressure and notify staff upon reaching a temperature threshold). This is up to the developer to write his own user story! Following that philosophy, nyukis are the nuts and bolts that helped design [Surycat](http://www.surycat.com).

Here is a list of core concepts tied to a nyuki:

* A nyuki runs as a standalone process
* A nyuki manages its own storage area (if it has data to store)
* A nyuki provides its own HTTP RESTful API
* A nyuki is connected to a bus for 1-to-many communication with other nyukis (currently using XMPP MUC or MQTT)

## Requirements
All you need is a Python interpreter. At the moment, only **Python 3.5** is supported.

## Getting started

Install the nyuki library:
```bash
pip install nyuki
```

Using *XMPP* as a bus service require some specific configuration:
* MUCs
* Automatic subscription

Nyuki's paradigms are convenient for Docker-based environment. We recommend using one container per nyuki implementation.

Let's now write two nyukis, namely `timon` and `pumba`. Each time `timon` gets a new message, `pumba` eats a larva (`timon.py` and `pumba.py` available in folder *examples*):

Here are [Timon's source](examples/timon.py) and [Pumba's source](examples/pumba.py).

Run your nyukis:

```bash
python timon.py -c timon.json
python pumba.py -c pumba.json
```

Play with it! Use your favorite HTTP tool (e.g. [Postman](https://chrome.google.com/webstore/detail/postman/fhbjgbiflinjbdggehcddcbncdddomop) or `curl`):

```bash
curl http://localhost:8080/v1/message
{"message": "hello world!"}

curl http://localhost:8081/v1/eaten
{"eaten": 0}

curl -H "Content-Type: application/json" -X PUT -d '{"message": "hello timon #1"}' http://localhost:8080/v1/message
curl http://localhost:8080/v1/message
{"message": "hello timon #1"}

curl http://localhost:8081/v1/eaten
{"eaten": 1}

curl -H "Content-Type: application/json" -X PUT -d '{"message": "hello timon #2"}' http://localhost:8080/v1/message
curl -H "Content-Type: application/json" http://localhost:8081/v1/eaten
{"eaten": 2}
```


## Configuration file

You must put the whole nyuki configuration into a JSON file:

```json
{
  "bus": {
    "jid": "sample@localhost",
    "password": "sample"
  },
  "api": {
    "host": "0.0.0.0",
    "port": 8081
  }
}
```

If no configuration file is given, a file named `default.json` will be used, and the same file will be used to create your configuration file is the one you specified does not exist.
Either way, it is always best to have a valid `default.json` nearby.
By the way, settings from the configuration file are overridden by command-line arguments. This can be useful to spawn several instances of the same nyuki quickly:

```bash
python sample.py -a 0.0.0.0:5558 -c sample.json
```

### Generic configuration

```json
{
    "api": {
        "host": "0.0.0.0",
        "port": 8081
    },
    "bus": {
        "service": "mqtt",
        "scheme": "ws",
        "host": "localhost",
        "name": "nyuki"
    },
    "version": 0
}
```

| Field | Description |
|-------|-------------|
| `api` | The nyuki api host and port |
| `bus` | The nyuki bus configuration see **Bus configuration** |
| `version` | The current configuration version. Versionning is used to be able to migrate config files cf [pijon](https://github.com/optiflows/pijon) |


Mandatory parameters are the Jabber ID (`jid`) and the password. Others are optional in both the command-line and the configuration file.

### Bus configuration

#### MQTT
```json
{
    "bus": {
        "service": "mqtt",
        "scheme": "ws",
        "host": "mosquitto",
        "name": "nyuki"
    },
}
```

| Field | Description |
|-------|-------------|
| `service` | the bus service used (mqtt or xmpp) |
| `scheme` | the scheme protocol used within mqtt options are 'ws': websocket, 'wss': websocket SSL, 'mqtt': MQTT, 'mqtts': MQTT SSL |
| `host` | the mqtt server host |
| `name` | the mqtt nyuki name |
| `keep_alive` | The keepalive set on your mqtt broker |
| `ping_delay` | Ping every `keep_alive - ping_delay` |


#### XMPP
```json
{
    "bus": {
        "certificate": "my_certif.crt",
        "host": "prosody",
        "jid": "nyuki@localhost",
        "password": "secure_password"
    }
}
```

| Field | Description |
|-------|-------------|
| `certificate` | An optional xmpp certificate file name to ensure the xmpp host validity during connection|
| `host` | The xmpp server host |
| `jid` | the xmpp jid for this nyuki, must be unique |
| `password` | the password associated with the jid |


#### Persistence

Bus events persistence can be enabled to ensure the delivery of every publication on the bus. These fields of the configuration file are available:

```json
{
    "bus": {
        "persistence": {
            "backend": "mongo",
            "host": "localhost",
            "ttl": 60,
            "memory_size": 1000
        }
    }
}
```

| Field | Description |
|-------|-------------|
| `backend` | The backend service used. Currently only 'mongo' is supported |
| `host` | The backend host name |
| `ttl` | the events ttl in minutes |
| `memory_size` | the number of events kept in memory (independently of the backend storage) |

## Workflow capabilities

Each and every nyuki has some workflow capabilities provided by [tukio](https://github.com/optiflows/tukio)

Meaning one can define templates in a nyuki and process workflows.
All workflow PAI entries are in the ressource /workflow (see the nyuki swagger: `GET http://host:port/<nyuki_name>/api/v1/swagger

### Mongo configuration (using `WorkflowNyuki`)

```json
{
    "mongo": {
        "host": "mongo",
        "database": "pipeline",
        "ssl": true,
        "ssl_certfile": "/mongo/mongo.pem",
        "ssl_cert_reqs": 0
    }
}
```

| Field | Description |
|-------|-------------|
| `host` | The mongo server host |
| `database` | The mongo database name |
| `ssl` | Connect to the db in ssl (default true) |
| `ssl_certfile` | the mongo ssl certificate file name |
| `ssl_cert_reqs` | do we need ot check the certificate validity |

### Tasks:
The following tasks may be used in any Nyuki workflow:

#### Factory
A task to do some string processing on the workflow data. see existing **String processing** item

```json
{
    "name": "factory",
    "id": "my_factory_task",
    "config": {"rulers": [
        {
            "type": "<rule-type-name>",
            "rules": [
                {"fieldname": "<name>"},
            ]
        }
    ]}
}
```

#### Sleep
A task that await a configurable time (in seconds)

```json
{
    "name": "sleep",
    "id": "my_sleeping_task",
    "config": {"time": 5}
}
```

#### Join
A dummy tasks that awaits from it's parents.

```json
{
    "name": "join",
    "id": "my_join_task",
    "config": {"wait_for": ["<task_id>"], "timeout": 60}
}
```


## String processing
Nyukis have string processing capabilities that can be used in workflow tasks (workflow task configuration) or on each bus input (`source_ruler` configuration)

### Extract

```json
{
    "rules": [
        {
            "fieldname": "key",
            "regexp": "[\d+]"
        }
    ],
    "type": "extract"
}
```

| Field | Description |
|-------|-------------|
| `fieldname` | The key where we want the extraction done and written |
| `regexp` | The regular expression |


### Sub

```json
{
    "rules": [
        {
            "fieldname": "key",
            "regexp": "[\d+]",
            "repl": "",
            "count": 1
        }
    ],
    "type": "extract"
}
```

| Field | Description |
|-------|-------------|
| `fieldname` | The key where we want the substitution done and written |
| `regexp` | The regular expression |
| `repl` | The replacement string |
| `count` | The number of matches to replace|


### Set

```json
{
    "rules": [
        {
            "fieldname": "key",
            "value": "new_value"
        }
    ],
    "type": "set"
}
```

| Field | Description |
|-------|-------------|
| `fieldname` | The key to set |
| `value` | The new value of the key |


### Unset

```json
{
    "rules": [
        {
            "fieldname": "key"
        }
    ],
    "type": "unset"
}
```

| Field | Description |
|-------|-------------|
| `fieldname` | the key to unset |


### Lookup

```json
{
    "rules": [
        {
            "fieldname": "key",
            ""
        }
    ],
    "type": "unset"
}
```

| Field | Description |
|-------|-------------|
| `fieldname` | the key to unset |


### Lower

```json
{
    "rules": [
        {
            "fieldname": "key",
        }
    ],
    "type": "lower"
}
```

| Field | Description |
|-------|-------------|
| `fieldname` | the key to lower |


### Upper

```json
{
    "rules": [
        {
            "fieldname": "key",
        }
    ],
    "type": "upper"
}
```

| Field | Description |
|-------|-------------|
| `fieldname` | the key transform in capital |



## Contributing

We always welcome great ideas. If you want to hack on the library, a [guide](CONTRIBUTING.md) is dedicated to it and describes the various steps involved.
