#!/usr/bin/env python3


""" This module serves an interface to the compiler tools.

Example:

    $ ipython
    In [1]: import library
    In [2]: import compiler
    In [3]: l = library.Library.load("../libs/musl/")
    In [4]: cflags = "-c -emit-llvm -g " + l.compiler_flags
    In [5]: compiler.compile_file("/tmp/isalnum.bc", "src/ctype/isalnum.c", cflags, l.directory)

    $ file /tmp/isalnum.bc
    /tmp/isalnum.bc: LLVM IR bitcode
"""

import subprocess
import os

TOOLS = os.path.abspath("../tools/llvm/build/Release+Asserts/bin")

COMPILER     = TOOLS + "clang"
LINKER       = TOOLS + "llvm-link"
ASSEMBLER    = TOOLS + "llvm-as"
DISASSEMBLER = TOOLS + "llvm-dis"

class CompileError(Exception):
    pass

class LinkerError(Exception):
    pass

def compile_collection(srcs, cflags, cwd):
    """ Compiles a collection srcs = {src: dest} """

    files, stats = list(), {'skipped': 0, 'compiled': 0, 'failed': 0, 'warning': 0}

    for src, dest in srcs.items():
        try:
            warning = compile_file(dest, src, cflags, cwd)
        except Exception as e:
            print(f"[!] Error ({src}):", e)
            stats['failed'] += 1
            continue

        if warning:
            #print(f"[!] Warning ({src}):", warning)
            stats['warning'] += 1

        stats['compiled'] += 1
        files.append(dest)

    return files, stats

def run_command(call, cwd=None):
    proc = subprocess.run(call, shell=True, stderr=subprocess.PIPE, cwd=cwd)

    if proc.returncode != 0:
        raise CompileError(proc.stderr.decode())

    return proc.stderr.decode() if proc.stderr else None

def compile_file(dest, src, cflags, cwd=None):
    """ This function invokes the compiler binary to generate a file dest based on cflags and on
    the input file src. It returns a warning string if the compiler raised one or None otherwise.
    """

    call = f"{COMPILER} {cflags} -o {dest} {src}"
    return run_command(call, cwd)

def link(dest, files, args=''):
    """ This function invokes the linker binary to link all files in the given list together.
    It returns a warning string if the linker raised one or None otherwise.
    """

    call = f"{LINKER} {args} -o {dest} {' '.join(files)}"
    return run_command(call)

def disassemble(dest, src):
    call = f"{DISASSEMBLER} -o {dest} {src}"
    return run_command(call)

def assemble(dest, src):
    call = f"{ASSEMBLER} -o {dest} {src}"
    return run_command(call)
