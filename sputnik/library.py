#!/usr/bin/env python3

import json
import os

class Build:
    FILENAME_NAME_MAPPING   = "rename_mapping.json"
    FILENAME_INCLUDED_FILES = "included_files.json"

    def __init__(self, directory, lib):
        self.dir, self.lib = directory, lib
        self.blob = os.path.join(self.dir, self.lib.name)

        self.name_mapping = dict()
        self.included_files = list()
        self.reload()

    def resolve_function(self, funcname):
        return self.name_mapping['@' + funcname][1:]

    def reload(self):
        self.name_mapping = self.load_name_mapping()
        self.included_files = self.load_included_files()

    def flush(self):
        self.name_mapping = dict()
        self.included_files = list()

    def load_included_files(self):
        p = os.path.join(self.dir, Build.FILENAME_INCLUDED_FILES)

        try:
            with open(p) as f:
                l = json.loads(f.read())
        except:
            l = list()

        return l

    def store_included_files(self, l):
        p = os.path.join(self.dir, Build.FILENAME_INCLUDED_FILES)

        with open(p, 'w') as f:
            f.write(json.dumps(l))

    def load_name_mapping(self):
        p = os.path.join(self.dir, Build.FILENAME_NAME_MAPPING)

        try:
            with open(p) as f:
                mapping = json.loads(f.read())
        except:
            mapping = dict()

        return mapping

    def store_name_mapping(self, mapping):
        p = os.path.join(self.dir, Build.FILENAME_NAME_MAPPING)

        with open(p, 'w') as f:
            f.write(json.dumps(mapping))

    def abspath(self, path):
        return os.path.join(self.dir, path)

class Library:
    CONFIGNAME = "config.json"

    @staticmethod
    def write_default_config(path, force=True):
        """ This method writes the default config to the given directory path. It overwrites
        an existing config if force is set to true. """

        default = json.dumps({
            "config_version": "0.0.1",
            "name": "<insert name of library>",
            "directory": "<insert current version directory>",
            "compiler_flags": "<insert compiler flags (like include flags)>",

            # these "traversals" list should hold every directory that
            # should be searched in order to find implementations. Add '.'
            # to invoke a greedy search.
            "traversals": [],
            "target": "./here_name_of_target.bc"
        }, indent=4)

        configfile = os.path.join(path, Library.CONFIGNAME)

        if os.path.isfile(configfile) and not force:
            raise Exception("file still exist")

        with open(configfile, 'w') as f:
            f.write(default)

    @staticmethod
    def load(libpath):
        """ This method loads a library by expecting the path to the library (not to config file,
        the place of config file is considered with Library.CONFIGNAME and this path) and returning
        a proper Library object """

        path = os.path.abspath(libpath)

        # read configuration:
        configfile = os.path.join(path, Library.CONFIGNAME)
        with open(configfile) as f:
            config = json.loads(f.read())

        if config['directory'].endswith('/'):
            config['directory'] = config['directory'][:-1]

        config['directory'] = os.path.join(path, config['directory'])
        config['builddir'] = config['directory'] + '-build'
        config['target'] = os.path.join(config['builddir'], config['target'])
        config['rename_mapping'] = os.path.join(config['builddir'], "rename_mapping.json")

        return Library(**config)

    def __init__(self, **kwargs):
        """ at least kwargs should hold: name, directory, builddir, compiler_flags, traversals
        where all are strings except from traversals which should be an iterable holding
        strings that define the directory names related to directory that should be considered
        of holding source files. """

        self.traversals = list()
        self.directory = str()
        self.builddir = str()
        self.target = str()
        self.rename_mapping = dict()

        for k, v in kwargs.items():
            setattr(self, k, v)

        self.build = Build(self.builddir, self)

    def load_rename_mapping(self):
        with open(self.rename_mapping) as f:
            m = json.loads(f.read())
        return m

    def sources(self):
        """ This method generates an iterable that yields every path to a source file that should
        be considered in build- or analysis process. This paths are relative to self.directory or
        to further builddirs (e.g. 'src/linux/link.c') """

        for traversal in self.traversals:
            if traversal.endswith('.c'):
                yield traversal
                continue

            # search in fld for source files:
            fld = os.path.join(self.directory, traversal)

            #for dirpath, dirnames, filenames in os.walk(fld):
            #    for filename in filter(lambda f: f.endswith('.c'), filenames):
            #        yield os.path.relpath(os.path.join(dirpath, filename), self.directory)

            # we do not want to have recursion so we switch to this snippet:
            for f in os.listdir(fld):
                fe = os.path.join(fld, f)
                if os.path.isfile(fe) and fe.endswith('.c'):
                    yield os.path.relpath(fe, self.directory)
