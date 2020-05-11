#!/usr/bin/env python3

from sputnik import compiler
from sputnik import tools
from sputnik.library import Library
from sputnik.rename import rename

import json
import logging
import os
import re
import shutil

class Builder:
    @staticmethod
    def invoke(lib, config, rebuild):
        b = Builder(lib)
        b.run(config, rebuild)

    def __init__(self, lib):
        self.lib = lib
        self.logger = logging.getLogger(lib.name)

    def pre_compile(self, rebuild):
        """ Build all files that are yielded by self.lib.sources(). It compiles them and writes
        it to self.lib.builddir.

        Args:
            rebuild: boolean that flags if the lib should be rebuild despite already built files

        Returns:
            A list of all considerable files (including all already built files and the new ones
        """

        # path to the file where we want to store all files that we built:
        included_files = os.path.join(self.lib.builddir, "included_files.json")

        old_files = list()

        cflags = "-S -emit-llvm -g -fno-builtin {0}".format(self.lib.compiler_flags)

        if rebuild:
            self.logger.debug("explicit rebuild")

            # cleanup before (re-) compiling and create builddir:
            shutil.rmtree(self.lib.builddir, ignore_errors=True)
            os.mkdir(self.lib.builddir)
        else:
            # try to load the list of those functions that we've already built:
            try:
                with open(included_files) as f:
                    old_files = json.loads(f.read())
            except:
                self.logger.debug("error rebuilding current state -> force explit rebuild")

                return self.pre_compile(rebuild=True)

        dest = lambda n: os.path.join(self.lib.builddir, n.rsplit('.', 1)[0] + '.ll')
        new_files = {src: dest(src) for src in self.lib.sources() if dest(src) not in old_files}

        # build directory structure in build directory:
        for f in new_files.values():
            try:
                os.makedirs(os.path.dirname(f))
            except FileExistsError:
                pass

        # compile every considerable file:
        compiled_files, stats = compiler.compile_collection(new_files, cflags, self.lib.directory)

        self.logger.debug( "compile statistics:")
        self.logger.debug(f"    compiled files: {stats['compiled']}")
        self.logger.debug(f"    skipped files:  {stats['skipped']}")
        self.logger.debug(f"    nr. failed:     {stats['failed']}")
        self.logger.debug(f"    nr. warnings:   {stats['warning']}")

        all_files = old_files + compiled_files

        # write every file that we've touched here in a list, so we know next
        # time which file should be already built.
        with open(included_files, 'w') as f:
            f.write(json.dumps(all_files, indent=4))

        return all_files

    def rename(self):
        """ Start the renaming process on generated self.lib.target.

        Returns:
            The mapping from rename.py
        """

        tmp_dir = tools.generate_tmp_dir()
        tmp_file = os.path.basename(self.lib.target).split('.')[0] + '.ll'

        file_ll = os.path.join(tmp_dir, tmp_file)
        file_ll_rn = os.path.join(tmp_dir, "new_" + tmp_file)

        self.logger.debug(f"tmp build dir is '{tmp_dir}'")

        compiler.disassemble(file_ll, self.lib.target)

        mapping = rename(file_ll_rn, file_ll, self.lib.name)

        # compile the renamed code stored in file_ll_rn and write it as
        # the used binary blob:

        shutil.copyfile(self.lib.target, self.lib.target + ".unrenamed")

        compiler.assemble(self.lib.target, file_ll_rn)
        tools.cleanup_tmp_dir(tmp_dir)

        return mapping

    def inject_wrappers(self, filename):
        """ This method compiles the given wrapper code into the lib build directory.
        It's used to include the call-wrappers.

        Returns:
            The filename of the new file in order to know the path that should be linked
            in at further processes.
        """

        cflags = "-S -emit-llvm -g -fno-builtin {0}".format(self.lib.compiler_flags)
        target = os.path.join(self.lib.builddir, "./wrapper.ll")
        compiler.compile_file(target, filename, cflags, self.lib.directory)
        return target

    def run(self, config, rebuild):
        """ Run the complete build process for that lib.

        Args:
            config: configuration holding at least the keys ['wrappers']
            rebuild: boolean that flags if the lib should be rebuild despite already built files
        """

        self.logger.info("start build process")

        files = self.pre_compile(rebuild)

        if config['wrappers']:
            w = os.path.abspath(config['wrappers'])
            self.logger.debug(f"inject wrappers '{w}'")
            files.append(self.inject_wrappers(w))

        self.logger.debug(f"link all files to '{self.lib.target}'")
        warn = compiler.link(self.lib.target, files)
        if warn:
            self.logger.warning(f"linker warning '{warn}'")

        self.logger.debug("rename content")
        mapping = self.rename()

        with open(self.lib.rename_mapping, 'w') as f:
            f.write(json.dumps(mapping, indent=4))

        # check integrity; check if every listed function is somehow inside that blob
        integrity_error = False
        for f in config['functions'].keys():
            f = '@' + f
            if f not in mapping.keys():
                integrity_error = True
                self.logger.warning(f"missing function '{f}'")

        if integrity_error:
            self.logger.error("integrity check failed")
        else:
            self.logger.info("integrity check passed")

        self.logger.info("build finished")

def build_call_wrappers(config):
    """ Generate the source and the header file for the call wrappers
    
    Args:
        config: dictionary serves at least 'function_list', 'wrappers_header' and 'wrappers' where
        all items serves the path to the proper file.
    """

    from sputnik.language import function_signature

    logger = logging.getLogger("call_wapper")

    logger.info("start building call wrappers")

    #with open(config['function_list']) as f:
    #    db = json.loads(f.read())

    db = config['functions']

    functions = [f for f in db.keys()]
    headers = set([e for l in db.values() for e in l])

    fd_s = open(config['wrappers'], 'w')
    fd_h = open(config['wrappers_header'], 'w')

    print("#ifndef __CALL_WRAPPERS", file=fd_h)
    print("#define __CALL_WRAPPERS", file=fd_h)
    print("", file=fd_h)

    # write defined header for every listed function to the source file:
    for header in headers:
        print(f"#include <{header}>", file=fd_s)
    print('', file=fd_s)

    # build definition and declaration for every listed function:
    for funcname in functions:
        logger.debug(f"considering function {funcname}")

        f = function_signature(funcname).fork(f"lib_entry_{funcname}")

        # generate the declaration:
        args = ', '.join([a.name for a in f.args])
        c = f.definition(f"return {funcname}({args});")

        # generate the definition:
        d = f.declaration()

        print(c, end='\n\n', file=fd_s)
        print(d, end='\n\n', file=fd_h)

    print("#endif", file=fd_h)

    fd_s.close()
    fd_h.close()

    logger.info("call wrappers built finished")

def main():
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-v', '--verbosity', action='count', help='increase output verbosity')
    parser.add_argument('-w', '--wrappers', action='store_true', help='rebuild call wrappers')
    parser.add_argument('-r', '--rebuild', action='store_true', help="don't consider existing compiled files")
    parser.add_argument('-c', '--config',  default='./configs/config_builder.json', help='path to wrapper file')
    args = parser.parse_args()

    # load config:
    with open(args.config) as f:
        config = json.load(f)

    # set logging (output) configuration:
    log_config = {
        'level': logging.WARNING,
        'format': "%(asctime)-8s | %(name)s | %(levelname)s | %(message)s",
        'datefmt': "%H:%M:%S"
    }

    if args.verbosity == 1:
        log_config['level'] = logging.INFO
    elif args.verbosity == 2:
        log_config['level'] = logging.DEBUG

    logging.basicConfig(**log_config)

    # build call wrappers
    if args.wrappers:
        build_call_wrappers(config)

    # run build process for every library:
    for lib in config['libs']:
        Builder.invoke(Library.load(lib), config, args.rebuild)

if __name__ == "__main__":
    main()

