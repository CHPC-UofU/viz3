#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
#
# Autogenerates a viz3 YAML config from Performance Co-Pilot using a pmproxy.
# The PCP tree hierarchy model doesn't perfectly match our graph structure,
# but the resulting graph is such that each indivdual metric is a node, and
# the metric's InDom (instances essentially. e.g. which CPU for a corresponding
# CPU metric) is another node that points to the metric.
#
# InDoms do not have nice human names, but rather descriptions, so the
# resulting node name is a mismash of the description and will probably need
# to be manually tweaked.
#
# Notably, the generation of the YAML requires a network request for every
# unique InDom, so the process may take a minute or so.
#
# Usage: generate-pcp-yaml.py [args] metrics-file
#     or generate-pcp-yaml.py [args] metric [metric ...]
#     or generate-pcp-yaml.py [args]
import argparse
import typing

import yaml

import viz3.datagraph.pcp as pcp


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="HTTP Proxy URL to retrieve Prometheus data through. e.g. "
             "socks5h://localhost:5555 with 'ssh -D5555 "
             "uNID@kingspeak.chpc.utah.edu' running in the background.",
    )
    parser.add_argument(
        "-t", "--target",
        type=str,
        default="localhost:44233",
        help="PCP PMProxy endpoint to query against. Defaults to "
             "'localhost:44233'."
    )
    parser.add_argument(
        "-m", "--metrics-file",
        required=False,
        type=str,
        help="File containing Prometheus metric names on their own line to "
             "generate YAML for."
    )
    parser.add_argument(
        "metrics",
        nargs="*",
        type=str,
        help="Metric names to generate YAML for"
    )
    args = parser.parse_args()
    return args


def format_yaml_from_metrics(querier: pcp.PMProxyQuerier,
                             metric_names: typing.Optional[typing.Set[str]] = None):
    metrics = querier.metrics(metric_names)
    if not metric_names:
        relevant_metrics = metrics
    else:
        relevant_metrics = [metric for metric in metrics if metric.name not in metric_names]

    indoms = []
    indom_strs_to_query = set(metric.indom_str for metric in relevant_metrics if metric.indom_str)
    for indom_str in indom_strs_to_query:
        indom = querier.indom(indom_str)
        indoms.append(indom)

    return pcp.format_yaml(querier, relevant_metrics, indoms)


def main(args):
    querier = pcp.PMProxyQuerier(args.target, proxy=args.proxy)

    metric_names = set(args.metrics) if args.metrics else []
    if args.metrics_file:
        with open(args.metrics_file) as f:
            metric_names.update(set(map(str.strip, f.readlines())))

    if not metric_names:
        metric_names = None

    yaml_str = format_yaml_from_metrics(querier, metric_names)
    print(yaml_str)


if __name__ == "__main__":
    args = parse_args()
    main(args)
