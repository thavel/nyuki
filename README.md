# Nyuki :bee:

[![Circle CI](https://circleci.com/gh/optiflows/nyuki.svg?style=svg&circle-token=13ac14e1fa136c3488cb48b32ce52347d398e08b)](https://circleci.com/gh/optiflows/nyuki)

## tl;dr
A lightweigh tool to build a nyuki. It provides features that shall help the developer with managing the following topics:

* Bus of communication between nyukis.
* Asynchronous events.
* Capabilities exposure through a REST API.

This library has been written to perform the features above in a reliable, single-threaded, asynchronous and concurrent-safe environment.
The core engine of a nyuki implementation is the asyncio event loop (a single loop is used for all features). A wrapper is also provide to ease the use of asynchronous calls over the actions nyukis are inteded to do.

## In the beginning was _**nyuki**_...
We have always thought **Surycat** as something that could mimic the extraordinary ability of humans to **create powerful communities**. Some of these communities are made of people with very different origins, backgrounds and even languages. But together, they can succeed in **reaching higher goals**.

At the time we started to shape Surycat, we quite naturally decided to look for a new software design approach that would empower our vision. At this time, we were inspired by **Agent-Oriented Programming (AOP)** which perfectly tied to our vision and could perfectly address most of our concerns: massively create communication channels, stay flexible and modular, ensure highly reliable and scalable system, easily extensible/new contributors-friendly.

We kept the concept of _agent_ for more than 3 years based on a basic -yet powerful- architectural design pattern: a source agent sends a message to the workflow agent which processes it and triggers actions performed by destination agents.
_[nice drawing to come...]_

As we went along the development of Surycat, we had to deal with pitfalls and accept concessions. Examples:
* Intermediate agents were created between the source and the workflow (e.g. `incomingcall` and `repeater`)
* Edge agents turned multi-protocols agents (e.g. `sms` and `email`)
* An update in the db model of one agent may impact the whole product (many migration issues)
* Redundant portion of codes (each with its own set of issues) because of unclear functional assumptions
* The expression _"agent-based"_ means _"install your software on all remote systems"_ in the U.S. which is the opposite of what Surycat does
* ...

By the beginning of 2015 everybody agreed that we couldn't stand for that situation longer. We had to define the concept of _agent_ and we also had to name it.

The new name for _agent_ is _**nyuki**_ which means _bee_ in Swahili ("Surycat" was inspired from the Disney movie "The Lion King" which extensively used Swahili words. An agent is a worker... like a bee!)

## Core concepts
These are the main assertions that help define what's a nyuki:

1. A **nyuki** is the base component of burrow. Any feature is provided through a nyuki!
2. A **nyuki** is standalone (no dependency, can be started individually)
3. A **nyuki** manages its own storage area (if it has to store data)
4. A **nyuki** is always connected to the bus
5. A **nyuki** must expose an API on the bus
6. A **nyuki** can communicate over the bus using either 1-to-1, 1-to-many and broadcast modes
7. A **nyuki** can extend the RESTful API of burrow
8. A **nyuki** may communicate with an external system. In that case, it is an _edge nyuki_ (others are core nyukies)
9. A **nyuki** has string/message processing capabilities embedded

## Edge niukies
As soon as a nyuki communicates with an external system (aka external to Surycat), it is known to be an _edge nyuki_. For a clean, powerful and easy-to-maintain architecture, we also decided to define additional guidelines for that category:

1. An **edge nyuki** must support only **1 protocol**
2. An **edge nyuki** must be able to **monitor the communication link** with the external system
3. Any protocol implementation used by an **edge nyuki** must be nyuki-independent (aka **protocol as a lib**)

<u>Note</u>: please refer to this [article](https://wiki.surycat.io/Specs/Monitoring) for more details about link monitoring.

## Guidelines
Let's dive a little bit into implementation details. The main idea in that section is to provide clear guidelines for a common structure to all nyukies.

**Parent process**
Starting a nuyki means starting a new process. This process should be interruptible at all time.

**Child processes and threads**
A nyuki must be able to manage its own child processes and threads; start/stop it whenever required. It has to monitor each process/thread so that it can restart it after any unexpected internal crash or failure. It must also report those crashes by sending an approriate message over the bus.

**Bus API**
Following the core concepts, a nyuki always expose an API on the bus. Here is a short list of requests that must be supported at all cases:
* `stop`: terminate all running tasks and stop the nuyki.
* `status`: request the global nyuki's status.
* `reset`: terminate all running tasks without restarting the nyuki.
* `reload`: dynamically reload the startup nyuki's configuration

**Afterglow**
When things go wrong, a nyuki must be designed to keep critical functions alive. For instance, if some threads/processes cannot be restarted after an internal failure, the nyuki must -as far as possible- be able to answer status request from other nyukies. It must also be able to report its "failure" status on the bus.

**Status**
All nyukies must be able to answer status requests from other nyukies, report status changes automatically and report any malfunction.

**Logging**
A nyuki must be able to log information whatever the execution environment and the errors that may arise. This is mandatory for efficient debugging. Default supported methods should be: `console`, `logfile` and `syslog`.

**Event-driven**
The recommended implementation for any nyuki follows the event-driven programming paradigm. Most of the time, a nyuki should only act on triggers (internal or external).

**Stateless**
A nuyki must answer to requests from the bus in a stateless fashion. Even nyukies that support stateful protocols should be designed following that principle (thanks to the clean spearation between the protocol and the nyuki layers).

**CLI**
It is highly recommended to provide a command-line interface (CLI) for each nyuki. That CLI should embed at least a short online help and may provide startup arguments and options.

**Configuration**
A nyuki may require to be configured to run properly. For instance, the current XMPP bus we use require to pass a Jabber-ID and a password at startup. A nyuki should be able to parse a configuration file as well as command-line arguments. As a well-known design pattern, command-line arguments should override parameters from the configuration file if both are provided at startup. Additional storages are also accepted.

**Storage backend**
A nyuki may have to store data for persistence. An external storage backend (simple file, SQL, NoSQL...) can be used in that case. Anyway, the nyuki should be designed to not fully rely on that backend (aka **loosely coupled**). If for any reason the storage backend was not available (at any time), the nyuki should be able to deliver -as far as possible- most of its service.
