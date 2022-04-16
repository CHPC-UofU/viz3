#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
#
# Autogenerates a viz3 YAML config from InfluxDB.
#
# The resulting graph structure is as follows:
#   - Each tag within a measurement is a node, called 'measurement_tag'
#   - Each field within a measurement is a node, called 'measurement_field', with
#     an edge between every measurement tag node and the field node.
#   - Each tag also has a parent tag node, called 'tag' that has an edge to
#     every 'measurement_tag' tag node.
#
# Usage: generate-influxdb-yaml.py [args]
import argparse
import logging
import os
import select
import sys

import viz3.datagraph.influx as influx
influx.logger.setLevel(logging.ERROR)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t", "--target",
        type=str,
        default="localhost:8086",
        help="InfluxDB endpoint to query against. Defaults to 'localhost:8086'."
    )
    parser.add_argument(
        "-u", "--username",
        type=str,
        help="The username to use."
    )
    parser.add_argument(
        "-p", "--password",
        type=str,
        required=False,
        help="The password to use. The password may also be passed from "
             "stdin, or provided in the INFLUX_PASSWORD environment variable."
    )
    parser.add_argument(
        "-d", "--database",
        type=str,
        help="The database to use."
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="HTTP Proxy URL to retrieve InfluxDB data through. e.g. "
             "socks5h://localhost:5555 with 'ssh -D5555 "
             "uNID@kingspeak.chpc.utah.edu' running in the background.",
    )
    args = parser.parse_args()
    return args


def main(args):
    password = ""
    if args.password:
        password = args.password
    # select returns subset of ready descriptors for each corresponding list
    # (4th arg is timeout): [read, write, execute]
    elif select.select([sys.stdin], [], [], 0.0)[0]:
        password = sys.stdin.readline().strip()
    else:
        try:
            password = os.environ["INFLUX_PASSWORD"]
        except KeyError:
            exit("No password provided by either -p/--password, stdin, or "
                 "INFLUX_PASSWORD environ")

    querier = influx.InfluxDBQuerier(
        host=args.target,
        database=args.database,
        username=args.username,
        password=password,
        proxy=args.proxy
    )
    measurements = influx.extract_measurements_from_influxdb(querier)
    print(influx.format_yaml(querier, measurements))


if __name__ == "__main__":
    main(parse_args())
