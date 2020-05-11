#!/usr/bin/env python3

""" This module is used to rename every symbol that is defined in the given code base.
It works on LLVM IR code.
"""

import re
import json

def detect_names(src, sub):
    """ This function detects every relevant symbol inside the file of given filename src
    and it returns a mapping of the original symbol to the new symbol that is
    derived by the given function sub.
    """

    mapping = dict()

    catchall = re.compile("(?:@(?P<variable_name>\\S+) = "
                          "(?!internal|private|appending|external).*|"
                          "define (?!internal|private)[^@]*"
                          "@(?P<function_name>[^(\"]+|\"[^\"]*\")\\(.*)[\n\r]*")

    with open(src) as fd_src:
        for line in fd_src:
            match = re.match(catchall, line)

            if match:
                if match.group("variable_name") is not None:
                    name = match.group("variable_name")
                    mapping['@' + name] = '@' + sub(name)
                elif match.group("function_name") is not None:
                    name = match.group("function_name")
                    mapping['@' + name] = '@' + sub(name)

    return mapping

def substitute(dest, src, mapping):
    """ This function substitutes every given symbol s in mapping.keys() by it's
    associated substitution in mapping[s] inside the given file src and
    writes the result to the given file named dest.
    """

    with open(src) as fin:
        content = fin.read()

    with open(dest, 'w') as fout:
        regex_match_symbols = re.compile('|'.join(map(re.escape, mapping)))

        for line in content.split('\n'):
            substitution = regex_match_symbols.sub(lambda match: mapping[match.group(0)], line)
            print(substitution, file=fout)

def rename(dest, src, prefix):
    """ This function renames every relevant symbol inside the file of given filename src
    by adding the given prefix to every symbol. It writes back the result to the file of
    given filename dest.
    """

    sub = lambda f: "{0}{2}_{1}".format(*re.match(r"([_]*)(.*)", f).groups(), prefix)

    mapping = detect_names(src, sub)
    substitute(dest, src, mapping)
    return mapping

def main():
    """ This function is called if this script should be run standalone. """
    import argparse

    parser = argparse.ArgumentParser(description='Rename Symbols in LLVM IR')
    parser.add_argument('-p', '--prefix', help='prefix that should be added to every symbol')
    parser.add_argument('-i', '--input', help='path to input file (content in LLVM IR)')
    parser.add_argument('-o', '--output', help='path to output file (writes LLVM IR)')
    parser.add_argument('-m', '--write-mapping', help='write mapping as json to file')
    parser.add_argument('-v', '--verbose', help='print rename mapping to stdout')
    args = parser.parse_args()

    mapping = rename(args.output, args.input, args.prefix)

    if args.write_mapping:
        with open(args.write_mapping, 'w') as f:
            json.dump(mapping, f, indent=4)

    if args.verbose:
        for name_old, name_new in mapping.items():
            print(name_old, "-->", name_new)

if __name__ == "__main__":
    main()
