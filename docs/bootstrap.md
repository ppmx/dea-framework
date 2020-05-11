# Bootstrap

## Overview

1. create a project directory for all tests and configuration files
2. create `functions/list.json` storing a dictionary describing all considerable functions
3. using `wrapper.py` to generate the call wrappers depending on listed functions
4. create a configuration for the prebuilding process
6. run `prebuild.py`


## Create function database

This function database assumes that equivalent functions of different implementations shares the same name
of it's headers. This assumption is valid at least for the application on libc's due to standardization of header
names.

An example of such database is:
```
{
	"fancy_function": ["header1.h", "header2.h"],
	"boring_function": ["boring/header.h"]
}
```

This mapping of function names to it's header files has to be stored under the
key 'functions' inside the builder configuration file. This database is used to generate
the call wrappers and to check the integrity of the builded blobs (that means that this
framework tries to detect if a expected function is missed inside the library blob).

## Configure the Builder

The builder needs some information to get his work done. This includes the following info's that
are stored in a json configuration file:

```
{
	"libs": ["path to libA", "path to libB"],
	"function_list": "path to the function database",
	"wrappers_header": "path to the file where call wrapper headers should be stored",
	"wrappers": "path to the file where implementation of the call wrappers should be stored",
	"functions": {}
}
```


## How-To Add a Library


### Summary:

1. create a folder for that library
2. download the current version and check signature (just for security :))
3. create a default config just to cover every setting
4. analyze the build process and set proper configuration
5. add the path to crafter and builder configuration
6. run the builder to prepare the library


### example work flow

```
$ mkdir ./libs/musl/
$ cd libs/musl/ && wget https://www.musl-libc.org/releases/musl-1.1.19.tar.gz{,.asc} && gpg -v *.asc && tar xfv *.tar.gz && cd -
$ ./introduce.py libs/musl/
```

Now we run the provided makefile once to get the proper compiler flags for that library and to
let the lib create the proper data structure inside that build directory.

In the end we evaluated the following configuration:

```
{
    "config_version": "0.0.1",
    "name": "musl",
    "directory": "musl-1.1.19",
    "compiler_flags": "-I./arch/x86_64 -I./arch/generic -Iobj/src/internal -I./src/internal -Iobj/include -I./include",
    "traversals": [long list of considerable source files]
}
```

And then we added 'libs/musl/' to the builder and the crafter configuration. *HINT: Experience shows that it's a good strategy to even grep
the function names inside the source directories in order to be able to find every necessary source file in a reasonable amount of time.*


## Invoke the Builder


Well, this step is easy:

```
$ ./prebuild.py -c ./path/to/config/file.json -vv -w -r
```

This step creates a build directory as subfolder of the library directory.
This directory contains a list of included files in the target blob (`included_files.json`),
the rename mapping (`rename_mapping.json`), the compiled source and call wrapper files
and two blobs. One of them is the target linkable blob after renaming all symbols (`$name.bc`)
and the other is before renaming all symbols (`$name.bc.unrenamed`).

