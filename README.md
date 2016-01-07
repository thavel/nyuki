# Nyuki :bee:

[![Circle CI](https://img.shields.io/circleci/project/optiflows/nyuki/master.svg)](https://circleci.com/gh/optiflows/nyuki) [![pypi version](http://img.shields.io/pypi/v/nyuki.svg)](https://pypi.python.org/pypi/nyuki) [![pypi download week](http://img.shields.io/pypi/dw/nyuki.svg)](https://pypi.python.org/pypi/nyuki)

## tl;dr
A lightweight Python library designed to implement agents (aka nyukis). It provides features that shall help developers with managing the following topics:

* Expose service features through a RESTful API
* Communication between nyukis (over HTTP and XMPP)
* Helpers for asyncio-based programming

This library has been written with a focus on reliability and developer-friendliness. Its design promotes single-threaded and asynchronous coding style through the extensive use of the [Python asyncio](https://docs.python.org/3/library/asyncio.html) event loop. A single loop is used to manage HTTP and XMPP-based communications as well as executing internal logic. Nyukis are suited for Agent-Oriented Programming and very useful to build distributed systems and scalable services.

## What is a nyuki?
A nyuki (a bee in Swahili) is an entity designed for real-time data processing (stream processing). Tying together several nyukis allows nearly unlimited use cases: from home automation (e.g. warm up my home when you're less than 5 miles away) to smart industries (lower down pressure and notify staff upon reaching a temperature threshold). This is up to the developer to write his own user story! Following that philosophy, nyukis are the nuts and bolts that helped design [Surycat](http://www.surycat.com).

Here is a list of core concepts tied to a nyuki:

* A nyuki runs as a standalone process
* A nyuki manages its own storage area (if it has data to store)
* A nyuki provides its own HTTP RESTful API
* A nyuki is connected to a bus for 1-to-many communication with other nyukis (currently using XMPP MUC)

## Requirements
All you need is a Python interpreter. At the moment, only **Python 3.4** is supported.

## Getting started
Don't bother with installing and configuring your own XMPP server at once! Run this preconfigured Docker image instead:

```bash
docker pull surycat/prosody
docker run -d surycat/prosody
```

Install the nyuki library:

```bash
pip install nyuki
```

Nyuki's paradigms are convenient for Docker-based environment. We recommend using one container per nyuki implementation.

Let's now write two nyukis, namely `timon` and `pumbaa`. Each time `timon` gets a new message, `pumbaa` eats a larva (`timon.py` and `pumbaa.py` available in folder *examples*):

```python
"""
This is 'timon'
"""
import logging
from nyuki import Nyuki, resource
from nyuki.capabilities import Response


log = logging.getLogger(__name__)


class Timon(Nyuki):

    message = 'hello world!'

    @resource(endpoint='/message')
    class Message:

        def get(self, request):
            return Response({'message': self.message})

        def post(self, request):
            self.message = request['message']
            log.info("message updated to '%s'", self.message)
            self.bus.publish({'order': 'go pumbaa!'})
            return Response(status=200)


if __name__ == '__main__':
    nyuki = Timon()
    nyuki.start()
```

```python
"""
This is 'pumbaa'
"""
import logging
from nyuki import Nyuki, resource
from nyuki.capabilities import Response


log = logging.getLogger(__name__)


class Pumbaa(Nyuki):

    message = 'hello world!'

    def __init__(self):
        super().__init__()
        self.eaten = 0

    async def setup(self):
        await self.bus.subscribe('timon', self.eat_larva)

    async def eat_larva(self, body):
        log.info('yummy yummy!')
        self.eaten += 1

    @resource(endpoint='/eaten')
    class Eaten:

        def get(self, request):
            return Response({'eaten': self.eaten})


if __name__ == '__main__':
    nyuki = Pumbaa()
    nyuki.start()
```

Run your nyukis:

```bash
python timon.py -j timon@localhost -p timon -a localhost:8080
python pumbaa.py -j pumbaa@localhost -p pumbaa -a localhost:8081
```

Play with it! Use your favorite HTTP tool (e.g. [Postman](https://chrome.google.com/webstore/detail/postman/fhbjgbiflinjbdggehcddcbncdddomop) or `curl`):

```bash
curl -H "Content-Type: application/json" http://localhost:8080/message
{"message": "hello world!"}

curl -H "Content-Type: application/json" http://localhost:8081/eaten
{"eaten": 0}

curl -H "Content-Type: application/json" -X POST -d '{"message": "hello timon #1"}' http://localhost:8080/message
curl -H "Content-Type: application/json" http://localhost:8080/message
{"message": "hello timon #1"}

curl -H "Content-Type: application/json" http://localhost:8081/eaten
{"eaten": 1}

curl -H "Content-Type: application/json" -X POST -d '{"message": "hello timon #2"}' http://localhost:8080/message
curl -H "Content-Type: application/json" http://localhost:8081/eaten
{"eaten": 2}
```

**Note**: find more code snippets in the folder *examples*.

## Configuration file
Instead of passing a list of arguments to the command-line you can put the whole nyuki configuration into a JSON file:

```json
{
  "bus": {
    "jid": "sample@localhost",
    "password": "sample"
  },
  "api": {
    "host": "0.0.0.0",
    "port": 5558
  }
}
```

Starting a nyuki with that config file gets dead simple:

```bash
python sample.py -c sample.json
```

By the way, settings from the configuration file are overridden by command-line arguments. This can be useful to spawn several instances of the same nyuki quickly:

```bash
python sample.py -j myjid@myhost -c sample.json
```

Mandatory parameters are the Jabber ID (`jid`) and the password. Others are optional in both the command-line and the configuration file.
