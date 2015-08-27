# Nyuki :bee:

[![Circle CI](https://circleci.com/gh/optiflows/nyuki.svg?style=svg&circle-token=13ac14e1fa136c3488cb48b32ce52347d398e08b)](https://circleci.com/gh/optiflows/nyuki)

## tl;dr
A lightweigh tool to build a nyuki. It provides features that shall help the developer with managing the following topics:

* Bus of communication between nyukis.
* Asynchronous events.
* Capabilities exposure through a REST API.

This library has been written to perform the features above in a reliable, single-threaded, asynchronous and concurrent-safe environment.
The core engine of a nyuki implementation is the asyncio event loop (a single loop is used for all features). A wrapper is also provide to ease the use of asynchronous calls over the actions nyukis are inteded to do.

## Usage
You can see Nyukis examples into the examples folder.  
You'll also find basic configuration files.  


Available configuration:  
- conf: The nyuki json configuration file to use  

configuration can also be overriden using command line parameters, see --help for more informations.  
- jid, password are required, they are the credentials for the nyuki to discuss on the bus.  
