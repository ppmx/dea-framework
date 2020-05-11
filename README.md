# Sputnik Documentation


## Installation

Run (for example): `sudo python3 ./setup.py install`.


## Bootstrap

In order to generate test cases there is some work that needs to be done in advance. This
includes the configuration of the build process and the crafting process but also the
compilation of any requested library.

See [docs/bootstrap.md](docs/bootstrap.md) for more information on how to setup the framework.


## Generate a Testcase

A testcase is described by the class `TestHarness`. After implementing the needed functionality
and deleting the superflous overloaded methods you may want to run this code and invoke the `runner`
method in order to generate the test blob.

See [docs/crafter.md](docs/crafter.md) for more information on how to configure the crafter process.


## current Issues
- currently ignoring compiler warnings. should be printable in the build process
- function pointer as arguments in signature
- nested pointers; auto-generation does not work properly
