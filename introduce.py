#!/usr/bin/env python3

# related documentation: docs/bootstrap.md

from sputnik.library import Library

def main():
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-f', '--force', action='store_true', help='overwrite existing config file')
    parser.add_argument('path', help='path to library (e.g. ./libs/diet/')
    args = parser.parse_args()

    Library.write_default_config(args.path, args.force)

if __name__ == "__main__":
    main()

