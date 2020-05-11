#!/usr/bin/env python3

""" It's just a toolbox serving various and sometimes useful functionality. """

import os
import shutil

def indent(code, indentation=1, indenter='\t'):
    line_indent = lambda line: indenter * indentation + line

    if isinstance(code, list):
        return [line_indent(line) for line in code]

    return line_indent(code)

def generate_tmp_dir(tmp='/tmp/', add='sputnik_'):
    """ Generate a temporary directory with random name.

    Args:
        tmp: path of forced parent directory
        add: prefix of the random generated name of the tmp directory

    Returns:
        A string holding the path to the random generated directory. This
        path is relative to the base of given tmp.
    """

    from random import choices
    from string import ascii_lowercase as alphabet

    while True:
        target = os.path.join(tmp, add + ''.join(choices(alphabet, k=11)))

        if not os.path.isfile(target):
            os.mkdir(target)
            return target

def cleanup_tmp_dir(dirname):
    """ Remove the temporary generated directory.

    Args:
        dirname: path to directory that should be deleted
    """

    shutil.rmtree(dirname)

def generate_signature_list(lst="../functions/list.json"):
    """ This is a helper function that prints every signature of every
    considerable function.

    Args:
        lst: path to list of function names
    """

    import json
    import language

    with open(lst) as fd_lst:
        db = json.loads(fd_lst.read())

    funcs = [ff for f in db.values() for ff in f]

    for func in funcs:
        print(language.function_signature_raw(func))

def copyfile(dest, src):
    """ This function copies a file.
    Args:
        dest: path to copy the file to
        src: path to file that should be copied
    """

    shutil.copyfile(src, dest)

def adjust_path(path, prefix=''):
    return os.path.abspath(os.path.join(prefix, path))

if __name__ == "__main__":
    generate_signature_list()
