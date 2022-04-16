#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
#
# Graphs the resuting node graph from a given viz3 yaml config file and either
# displays it or writes out a DOT (.dot) file.
#
# Usage: ./graph-yaml.py [args] yaml-file
import argparse
import os
import sys
import threading
import time

import viz3.datagraph


def parse_args():
    parser = argparse.ArgumentParser()
    output_args = parser.add_mutually_exclusive_group()
    output_args.add_argument(
        "-o", "--output-dot",
        default="/dev/stdout",
        type=str,
        help="Whether to output the data graph in dot format"
    )
    output_args.add_argument(
        "-s", "--show",
        action='store_true',
        help="Whether to show the data graph in a window"
    )
    parser.add_argument("yaml_file", help="Path to YAML file that defines the datasources")
    args = parser.parse_args()
    if not os.path.isfile(args.yaml_file):
        print("YAML file given does not exist: " + args.yaml_file, file=sys.stderr)
        sys.exit(2)

    return parser.parse_args()


def main(args):
    data_graph = viz3.datagraph.YamlReader.from_file(args.yaml_file)

    if args.output_dot:
        data_graph.write_dot(args.output_dot)
    if args.show:
        data_graph.draw()


if __name__ == "__main__":
    args = parse_args()
    main(args)
