#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
#
# Autogenerates a viz3 YAML config from Prometheus using an assortment of
# heuristics. The heuristics work better on larger time ranges, though they
# are also exponentially expensive, so a tradeoff must be made.
#
# The heuristics are also not perfect, and will likely have to be tweaked.
#
# Usage: generate-prometheus-yaml.py [args] metrics-file
#     or generate-prometheus-yaml.py [args] metric [metric ...]
import argparse
import collections
import datetime
import itertools
import typing

import more_itertools

import viz3.datagraph.prometheus as prometheus


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
        default="localhost:9090",
        help="Prometheus endpoint to query against. Defaults to "
             "'localhost:9090'."
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=60 * 60 * 24 * 14,  # two weeks
        help="Period in seconds to go back in time when looking at metrics. Defaults to two weeks."
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


def non_empty_powerset(iterable):
    """
    Returns the powerset of the iterable, without an empty tuple.
    """
    yield from filter(
        lambda g: g != tuple(),
        more_itertools.powerset(iterable)
    )


def identify_alias_label_names(label_maps):
    """
    Groups label names together by whether they change together in the label
    maps. i.e. identifies "aliased" label names. Returns a set of label name
    tuples, each tuple corresponding to a group that changes together.
    """
    assert more_itertools.all_equal(set(label_map.keys()) for label_map in label_maps)
    label_names = set(label_maps[0].keys())

    # FIXME: Use asymetry of label equality here; we are doing more than
    #        necessary work
    names_changed_together = {
        name: label_names.copy()
        for name in label_names
    }
    label_maps_iter = iter(label_maps)
    prev_label_map = next(label_maps_iter)
    for label_map in label_maps_iter:
        did_values_change = {
            name: value == prev_label_map[name]
            for name, value in label_map.items()
        }
        for name, value_changed in did_values_change.items():
            for other_name in names_changed_together[name].copy():
                if did_values_change[other_name] != value_changed:
                    names_changed_together[name].discard(other_name)

        prev_label_map = label_map

    return set(
        tuple(group)
        for group in names_changed_together.values()
    )


def is_distinguishing_label_name_groups(label_name_groups, label_maps):
    """
    Returns whether the set of label name groups (each name in a group being
    an alias of one another) uniquely identifies all a metric value.
    """
    names_allowed_to_change = set(more_itertools.flatten(label_name_groups))

    # FIXME: Is this completely correct? I think supersets of the
    #        distinguishing label name set might return True here... which is
    #        fine?
    label_maps_iter = iter(label_maps)
    prev_label_map = next(label_maps_iter)
    for label_map in label_maps_iter:
        changed_label_names = {
            name
            for name, value in label_map.items()
            if value != prev_label_map[name]
        }
        if not set(changed_label_names).issubset(names_allowed_to_change):
            return False

        prev_label_map = label_map

    return True


def identify_distinguishing_label_names(label_name_aliases, label_maps):
    """
    Finds the subset of labels in the label maps which distingish metric
    values. Returns a list of label names.
    """
    first_label_name_to_group_map = {group[0]: group for group in label_name_aliases}
    # powerset will return the largest first; we want the largest label name
    # group so break early
    for label_name_set in non_empty_powerset(first_label_name_to_group_map.keys()):
        label_name_set_groups = {
            first_label_name_to_group_map.get(name, tuple(name))
            for name in label_name_set
        }
        if is_distinguishing_label_name_groups(label_name_set_groups, label_maps):
            return label_name_set

    assert False  # how?! Doesn't prometheus enforce that a label set is unique?


def partition_label_maps_by_nameset(label_maps):
    """
    Partitions the list into sublists where each element has the same set of
    label names.
    """
    partitioned_label_maps = collections.defaultdict(list)
    for label_map in label_maps:
        key = tuple(label_map.keys())
        partitioned_label_maps[key].append(label_map)

    return list(partitioned_label_maps.values())


def order_identifying_label_names_heuristic(identifying_label_names, label_maps):
    """
    Orders the label names such that the previous label should
    "distingish" the current label.
    e.g. [disk, hostname, mount] -> [hostname, disk, mount]
    """
    # This is a technique that avoids having to find uniqueness on a per-label
    # basis, mainly because it's easier to understand/write, but also it's quick
    per_label_unique_values = collections.defaultdict(set)
    for label_map in label_maps:
        for id_label_name in identifying_label_names:
            per_label_unique_values[id_label_name].add(label_map[id_label_name])

    return sorted(identifying_label_names, key=lambda name: len(per_label_unique_values[name]), reverse=True)


def order_identifying_label_names_bad_heuristic(label_name_groups, label_maps):
    """
    Orders the label name groups such that the previous label should
    "distingish" the current label.
    e.g. [disk, hostname, mount] -> [hostname, disk, mount]

    NOTE: Currently this function is exponentially expensive and not very
          good. In some cases it's better than the other heuristic, but
          when it is not, it is terrible.
    """
    first_label_to_group_map = {
        next(iter(group)): group
        for group in label_name_groups
    }
    first_label_names = list(first_label_to_group_map.keys())
    order = first_label_names.copy()

    for first_label, second_label in itertools.combinations(first_label_names, 2):
        first_value_counts = collections.defaultdict(int)
        first_value_second_counts = collections.defaultdict(lambda: collections.defaultdict(int))
        for label_map in label_maps:
            first_value = label_map[first_label]
            first_value_counts[first_value] += 1
            second_value = label_map[second_label]
            first_value_second_counts[first_value][second_value] += 1

        max_first_count = 0
        max_second_count = 0
        for first_unique_value, first_count in first_value_counts.items():
            max_first_count = max(first_count, max_first_count)
            max_second_count = max(first_value_second_counts[first_unique_value].values())

        i = order.index(first_label)
        j = order.index(second_label)
        if max_first_count > max_second_count and i > j:
            order[i], order[j] = order[j], order[i]
        elif max_second_count > max_first_count and i < j:
            order[j], order[i] = order[i], order[j]

    return [first_label_to_group_map[label] for label in order]


def identify_informative_label_names(identifying_label_names, label_name_aliases, label_maps):
    """
    Returns a set of label names that adds informative information for each
    distinct value. e.g. ifAlias with SNMP would be an informative label name
    (if it wasn't considered an alias, which depends on how vendors and
     sysadmins treat it).

    Note: An informative label might also serve as a "category". e.g. the job
          label, which yes, adds information, but it serves to categorize
          metrics (the __name__ label). In other words, only a subset of the
          label names returned here add information for _this particular_
          metric.
    """
    assert more_itertools.all_equal(set(label_map.keys()) for label_map in label_maps)

    unknown_label_names = set(label_maps[0].keys())
    for id_label_name in identifying_label_names:
        unknown_label_names.discard(id_label_name)
        for alias_group in label_name_aliases:
            if id_label_name in alias_group:
                for label_name_alias in alias_group:
                    unknown_label_names.discard(label_name_alias)

    return unknown_label_names


def identify_label_name_categories(category_label_names, primary_label_names, all_label_maps):
    """
    Finds the list of labels that each category label refines. e.g. for a 'job'
    label, a refinement label might be 'instance'.

    Returns a dictionary mapping category label names to a set of refinement
    label names.
    """
    category_refinement_label_names = {}

    # Essentially, for each category _value_ (for each category, for each
    # category value), figure out if the values of each other set of labels is
    # distinct from each other category value.
    #
    # Of course this is extremely messy because we only want to iterate over
    # the (many) label maps once per category, and also because the set of
    # labels across different label maps is not the same...
    for category_label_name in category_label_names:
        per_value_primary_label_values = collections.defaultdict(  # per-category value
            lambda: collections.defaultdict(set)  # per-label set of (primary label) values
        )
        category_primary_label_names = primary_label_names - {category_label_name}
        common_primary_label_names = primary_label_names.copy()
        for label_map in all_label_maps:
            category_value = label_map.get(category_label_name, "")
            # copy -> mutating while iterating
            for primary_label_name in category_primary_label_names:
                if primary_label_name not in label_map:
                    common_primary_label_names.discard(primary_label_name)
                    continue

                primary_label_value = label_map[primary_label_name]
                per_value_primary_label_values[category_value][primary_label_name].add(primary_label_value)

        possible_refinement_label_names = common_primary_label_names.copy()
        for primary_label_name in common_primary_label_names:
            # are set of values in each category value distinct?
            shared_set_of_values = set()
            for category_values in per_value_primary_label_values.values():
                primary_label_values = category_values[primary_label_name]
                shared_set_of_values.intersection_update(primary_label_values)

            if len(shared_set_of_values) > 0:
                possible_refinement_label_names.remove(primary_label_name)

        category_refinement_label_names[category_label_name] = possible_refinement_label_names

    return category_refinement_label_names


def _try_extract_relationship_from_metric(querier: prometheus.PrometheusQuerier, metric_name: str,
                                          start: datetime.datetime, end: datetime.datetime) \
        -> typing.Optional[prometheus.PrometheusMetricRelationship]:
    label_maps = querier.series([metric_name], start, end)
    if not label_maps:
        return None

    for label_map in label_maps:
        label_map.pop("__name__")  # No need for this; might cause confusion in algorithms

    common_label_names = set(label_maps[0].keys())
    for label_map in label_maps[1:]:
        common_label_names.intersection_update(set(label_map.keys()))

    stripped_label_maps = [{
        label_name: label_map[label_name]
        for label_name in common_label_names
    }
        for label_map in label_maps
    ]

    # Some labels change together. i.e. aliases. The SNMP ifIndex and ifName
    # labels are an example of this; ifAlias is not necessarily an alias
    # because vendors (and perhaps sysadmins) may not put distinct values for
    # the distict interfaces, messing up the "change together" logic (they are,
    # in my view, added information, NOT aliases).
    label_name_aliases = identify_alias_label_names(stripped_label_maps)

    # Capture the smallest set of labels that distinguish one metric value
    # from another; it is possible there are multiple sets of values here. I'm
    # not sure the right approach for that case (if it is indeed a real case),
    # so smallest works for now
    identifying_label_names = identify_distinguishing_label_names(
        label_name_aliases,
        stripped_label_maps
    )

    # When we create the graph, we want a series of nodes, each node
    # corresponding to an identifying label group, connected to one other with
    # the last node connecting to a node which contains a metric value, like a
    # tree with metric value leaves. The top levels of the graph/tree should
    # be the least "specific" label. i.e. the labels that change the least so
    # the tree/graph levels are ordered by specificity (e.g. a hostname label
    # should be above a interface label, since a interface is on a
    # per-hostname basis). Order here.
    ordered_identifying_label_names = order_identifying_label_names_heuristic(
        identifying_label_names,
        stripped_label_maps
    )

    # Some labels are purely informational; we want these as values. Note that
    # informative here, does not mean that the information is exclusive to
    # this metric, or the logical metric series. Categories (labels that
    # categorize a subset of identifying labels across non-logical metric
    # series) are  included in this set
    value_label_names = identify_informative_label_names(
        identifying_label_names,
        label_name_aliases,
        stripped_label_maps
    )

    return prometheus.PrometheusMetricRelationship(
        metric_name,
        ordered_identifying_label_names,
        {tuple(alias_group) for alias_group in label_name_aliases if len(alias_group) > 1},
        value_label_names,
        # FIXME: automatically find label_values mappings
        {},
        [],
    )


def format_yaml_from_metrics(querier: prometheus.PrometheusQuerier,
                             metrics: typing.List[str],
                             start: datetime.datetime,
                             end: datetime.datetime):
    metric_relationships = []
    valid_metrics = []
    for metric in metrics:
        maybe_relationship = _try_extract_relationship_from_metric(querier, metric, start, end)
        if not maybe_relationship:
            continue

        metric_relationships.append(maybe_relationship)
        valid_metrics.append(metric)

    if not metric_relationships:
        return

    label_categories = {}

    value_label_names_in_relations = [rel.value_label_names for rel in metric_relationships]
    shared_label_names = value_label_names_in_relations[0].intersection(*value_label_names_in_relations[1:])
    primary_label_names = set(rel.primary_label_names[0] for rel in metric_relationships)

    if shared_label_names:
        all_label_maps = querier.series(valid_metrics, start, end)
        label_categories = identify_label_name_categories(shared_label_names, primary_label_names, all_label_maps)
        for label_category_name, associated_label_names in label_categories.items():
            # The value labels names might contain categories simply because
            # we pull out value label names on a per-metric basis and
            # categories apply across labels
            for relationship in metric_relationships:
                relationship.value_label_names.discard(label_category_name)

    return prometheus.format_yaml(querier, metric_relationships, label_categories)


def main(args):
    querier = prometheus.PrometheusQuerier(args.target, proxy=args.proxy)
    end = datetime.datetime.now()
    start = end - datetime.timedelta(seconds=args.seconds)

    metrics = list(args.metrics)
    if args.metrics_file:
        with open(args.metrics_file) as f:
            metrics.extend(list(map(str.strip, f.readlines())))

    if not metrics:
        exit("No metrics given in either the file or arguments")

    yaml_str = format_yaml_from_metrics(querier, metrics, start, end)
    print(yaml_str)


if __name__ == "__main__":
    args = parse_args()
    main(args)
