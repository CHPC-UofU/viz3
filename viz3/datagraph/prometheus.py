# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Defines a Prometheus data source according to datagraph.py.
"""
import abc
import collections
import copy
import dataclasses
import datetime
import enum
import functools
import itertools
import logging
import re
import typing

import more_itertools

from .. import datagraph
from .. import acache

import requests

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PrometheusQuerier:
    """
    A wrapper around Prometheus' HTTP API.
    """

    def __init__(self, prometheus_target: str, proxy: typing.Optional[str] = None,
                 cache: typing.Optional[acache.AbstractCache] = None):
        self._target = prometheus_target
        self._cache: acache.AbstractCache = acache.NopCache()
        if cache is not None:
            self._cache = cache

        self._proxy = {}
        if proxy is not None:
            self._proxy = {"http": proxy}

    def cache(self) -> acache.AbstractCache:
        return self._cache

    def target(self):
        return self._target

    def proxy(self):
        return self._proxy

    @acache.class_fallback_cache
    def query_range_and_group_by_label(self, query, id_label, start_dt, end_dt, step_secs=60*5) \
            -> typing.Dict[datetime.datetime, typing.Dict[str, float]]:
        """
        Given a Prometheus query and a identifying label (uniquely identifies
        each particular value. e.g. 'instance' or 'agent' for SNMP queries),
        returns a nested dictionary where the outer keys are datetime objects,
        and the inner dictionary contains keys identifying label values and
        Prometheus values.

        >>> querier = PrometheusQuerier("localhost:9090")
        >>> querier.query_range_and_group_by_label(
        ...     "measurementsInletSensorValue{sensorType="5"}", # power
        ...     "instance",                                     # id by instance label
        ...     datetime.datetime.now() - datetime.timedelta(days=7),
        ...     datetime.datetime.now(),
        ...     60 * 15                                         # return values for every 15 mins
        ... )
        {
            datetime.datetime(2021, 8, 25, 21, 30, 4, 337817): {
                "ddc-infra-pdu-v1-1": 43210.0,
                "ddc-infra-pdu-v2-1": 54321.0
            },
            ...
        }
        """
        logger.debug("executing query_range %s (%s-%s/%s)", query, start_dt, end_dt, step_secs)

        # See https://prometheus.io/docs/prometheus/latest/querying/api/
        resp = requests.get(
            "http://{}/api/v1/query_range".format(self._target),
            params={
                "query": query,
                "start": start_dt.strftime("%s"),
                "end": end_dt.strftime("%s"),
                "step": step_secs,
            },
            proxies=self._proxy
        )
        results =  resp.json()["data"]["result"]

        time_id_value_map = collections.defaultdict(dict)
        for result in results:
            id_label_value = result["metric"][id_label]
            for ts, value in result["values"]:
                time_id_value_map[ts][id_label_value] = float(value)

        return time_id_value_map

    @acache.class_fallback_cache
    def query(self, query: str):
        """
        Given a Prometheus query, returns a list of tuple results, with each
        result containing a dictionary of label names to label values and the
        corresponding value.
        """
        logger.debug("executing query %s", query)

        # See https://prometheus.io/docs/prometheus/latest/querying/api/
        resp = requests.get(
            "http://{}/api/v1/query".format(self._target),
            params={"query": query},
            proxies=self._proxy
        )

        # {
        #   "status": "success",
        #   "data": {
        #     "resultType": "vector",
        #     "result": [
        #       {
        #         "metric": {
        #           "__name__": "ifHCOutOctets",
        #           "ifDescr": "eth0",
        #           "ifIndex": "2",
        #           "instance": "frisco1.wasatch.peaks",
        #         },
        #         "value": [
        #           1634834329.256,
        #           "1980233568351"
        #         ]
        #       },
        #       ...
        results = resp.json()["data"]["result"]

        to_return = []
        for result in results:
            label_dict = result["metric"]
            ts, value = result["value"]
            to_return.append((label_dict, value))

        return to_return

    def query_and_group_by_label(self, query, id_label):
        """
        Given a Prometheus query and a identifying label (uniquely identifies
        each particular value), returns a dictionary where the outer keys
        identify id label values and the values are the corresponding
        Prometheus value.
        """
        id_value_map = {}
        for label_dict, value in self.query(query):
            id_value_map[label_dict[id_label]] = value

        return id_value_map

    @acache.class_fallback_cache
    def series(self, metrics, start_dt, end_dt):
        """
        Returns a list of time-series from Prometheus, where each item in the
        list is a dictionary mapping labels to a value.
        """
        logger.debug("executing series %s (%s-%s)", metrics, start_dt, end_dt)

        # See https://prometheus.io/docs/prometheus/latest/querying/api/
        resp = requests.get(
            "http://{}/api/v1/series".format(self._target),
            params={
                "match[]": list(metrics),
                "start": start_dt.strftime("%s"),
                "end": end_dt.strftime("%s"),
            },
            proxies=self._proxy
        )

        series = resp.json()["data"]

        series_labels = []
        for label_dict in series:
            # copy -> in case requests does funky things; no need for deep
            #         copy, since (presumably) all keys and values are strings
            #         which are immutable
            series_labels.append(label_dict.copy())

        return series_labels

    @acache.class_fallback_cache
    def metadata(self):
        """
        Returns a dictionary of all metrics in Prometheus, where each key is
        the metric name and the value is a list of dictionaries containing each
        unique metric "type", "help", and "unit" properties.
        """
        logger.debug("executing metadata")

        # See https://prometheus.io/docs/prometheus/latest/querying/api/#querying-metric-metadata
        resp = requests.get(
            "http://{}/api/v1/metadata".format(self._target),
            proxies=self._proxy
        )
        return resp.json()["data"]

    @acache.class_fallback_cache
    def label_values(self, label_name):
        """
        Returns a list of label values for the given label name.
        """
        logger.debug("executing label_values %s", label_name)

        resp = requests.get(
            "http://{}/api/v1/label/{}/values".format(self._target, label_name),
            proxies=self._proxy
        )
        return list(resp.json()["data"])


class PrometheusDataGraph(datagraph.DataGraph):

    def __init__(self, querier: PrometheusQuerier, datasource_name: str):
        super().__init__()
        self._querier = querier
        self._datasource_name = datasource_name

    def find_by_label_name(self, label_name: str):
        return self.find(self._datasource_name, label_name)

    def _create_prometheus_label(self, label_name: str):
        return PrometheusLabel(
            self._querier,
            self._datasource_name,
            label_name,
        )

    def construct_prometheus_label(self, label_name: str, from_label: typing.Optional['PrometheusLabel'] = None):
        label_node = self._create_prometheus_label(label_name)
        self.add_node(label_node, from_label)
        return label_node

    def _create_prometheus_derived_label(self, derivation: 'PrometheusLabelDerivation'):
        return PrometheusDerivedLabel(
            self._querier,
            self._datasource_name,
            derivation.target_label_name,
            derivation.new_label_name,
            derivation.derivation_funcs,
            derivation.default_or_none
        )

    def construct_derived_prometheus_label(self, derivation: 'PrometheusLabelDerivation',
                                           from_label: typing.Optional['PrometheusLabel'] = None):
        new_derived_node = self._create_prometheus_derived_label(derivation)
        target_node = self.find_by_label_name(derivation.target_label_name)
        self.add_edge_node(target_node, new_derived_node)
        self.add_node(new_derived_node, from_label)

        if derivation.parent_label_name:
            parent_label_node = self.find_by_label_name(derivation.parent_label_name)
            self.add_edge_node(parent_label_node, new_derived_node)

        return new_derived_node

    def construct_prometheus_label_aliases(self, label_name_aliases: typing.Set[str]):
        label_nodes = {}
        for label_name in set(label_name_aliases):
            try:
                aliased_label_node = self.find_by_label_name(label_name)
            except ValueError:
                aliased_label_node = self._create_prometheus_label(label_name)

            label_nodes[label_name] = aliased_label_node

        for label_name, label_node in label_nodes.items():
            for other_label_node in [node for name, node in label_nodes.items() if name != label_name]:
                self.add_node_next_to(label_node, other_label_node)

    def _create_prometheus_metric(self, metric_name: str):
        return PrometheusMetric(
            self._querier,
            self._datasource_name,
            metric_name,
        )

    def construct_prometheus_metric_to_all(self, metric_name: str):
        metric_node = self._create_prometheus_metric(metric_name)
        for label_node in self.nodes():
            self.add_leaf(metric_node, label_node)
        return metric_node

    def construct_prometheus_metric(self, metric_name: str, *from_label_nodes: 'PrometheusLabel'):
        metric_node = self._create_prometheus_metric(metric_name)
        for from_label_node in from_label_nodes:
            self.add_leaf(metric_node, from_label_node)
        return metric_node

    def _create_prometheus_adapted_metric(self, original_metric_name: str, new_metric_name: str,
                                          enumerated_label_name: str, fixed_value: typing.Any):
        return PrometheusEnumMetric(
            querier=self._querier,
            datasource_name=self._datasource_name,
            target_metric_name=original_metric_name,
            new_metric_name=new_metric_name,
            enumerated_label_name=enumerated_label_name,
            fixed_label_value=str(fixed_value)
        )

    def construct_prometheus_enum_metric(self, original_metric_name: str, new_metric_name: str,
                                         enumerated_label_name: str, fixed_value: typing.Any,
                                         from_label_node: 'PrometheusLabel'):
        metric_node = self._create_prometheus_adapted_metric(
            original_metric_name=original_metric_name,
            new_metric_name=new_metric_name,
            enumerated_label_name=enumerated_label_name,
            fixed_value=str(fixed_value)
        )
        self.add_leaf(metric_node, from_label_node)
        return metric_node


class PrometheusNode(datagraph.DataNode, abc.ABC):
    """
    An abstract class for storing Prometheus data within a node, along with a
    query object that is used for retrieving values.
    """

    def __init__(self, querier: PrometheusQuerier, datasource_name: str, name: str):
        super().__init__(datasource_name, name, str)
        self._querier = querier

    def canonical_label_name(self) -> str:
        raise NotImplementedError()

    def label_matches(self) -> typing.Tuple[str, ...]:
        raise NotImplementedError()

    def querier(self):
        return self._querier

    def result(self) -> 'PrometheusResult':
        raise NotImplementedError()


class PrometheusLabel(PrometheusNode):
    """
    Stores a Prometheus label within a node.
    """

    def __init__(self, querier: PrometheusQuerier, datasource_name: str, label_name: str):
        super().__init__(querier, datasource_name, label_name)

    def label_name(self):
        return self.name()

    def canonical_label_name(self):
        return self.label_name()

    def label_matches(self) -> typing.Tuple[str, ...]:
        # This strange regex is because Prometheus does not allow queries
        # against it where all of the labels have empty matchers. e.g.
        # {instance=~".*"} or {instance=~"^.*$", label=~"^.*$"}
        # (I my mind this should return all series where instance is defined,
        #  and where both instance and label are defined for the second)
        #
        # This is not OK for us, because we sometimes want all unique tuples
        # of a label set, (e.g. (instance, gpu)) regardless of what metrics
        # are associated with that tuple.
        #
        # Furthermore, when an "empty" matcher is provided with another label
        # match that is not empty (e.g. {instance=~".*", gpu="1"}), the empty
        # matched label is not required to exist in each metric series
        # returned. In other words, an empty matcher specified is essentially
        # ignored by Prometheus. Perhaps this is why we cannot have all empty
        # matched labels.
        #
        # So our hack is to give a "non-empty" match that Prometheus accepts,
        # but really is going to match everything. I doubt newlines are
        # used (\v). Plus \v, unlike \r or \n doesn't mess up logs.
        return (
            r'{}=~"^[^\v].*$"'.format(self.canonical_label_name()),  # [^...] -> characters NOT in [] set
        )

    def result(self):
        return PrometheusLabelResult(self)


DerivationFunc = typing.Callable[[str], str]


class PrometheusDerivedLabel(PrometheusLabel):
    """
    A fake label whose values are derived from a target label. A derivation is
    simply a list of functions that take in a string and return a new string
    that are applied to each label value from the target label.

    e.g. one might want to derive a fake 'datacenter' label from a 'location'
         label with values ["DDC u5", "DDC u6"] derived into ["ddc", "ddc"].

    This is not to be confused with an adaptor, found in datagraph.py, which
    is meant to adapt the values of graph nodes from different data sources
    so that they can be joined together. The primary difference is that an
    adaptor does not introduce a new node in the graph that is queryable by
    the user, whereas a derived label does. The former _adapts_ the values
    of a node to fit another node, and the latter _derives_ new queryable
    values from a node.
    """

    def __init__(self, querier: PrometheusQuerier, datasource_name: str,
                 target_label_name: str, new_label_name: str,
                 derivation_funcs: typing.List[DerivationFunc],
                 default_or_none: typing.Optional[str] = None):
        super().__init__(querier, datasource_name, new_label_name)
        self._target_label_name = target_label_name
        self._derivation_funcs = derivation_funcs
        self._default_or_none = default_or_none

    def canonical_label_name(self):
        return self._target_label_name

    def apply_derivation(self, to_label_value: str) -> typing.Optional[str]:
        new_value = to_label_value
        for derivation_func in self._derivation_funcs:
            try:
                new_value = derivation_func(new_value)
            except Exception:
                # if derivations throw errors, they are indicating
                # that a derivation could not be performed so we should
                # indicate that to the caller if there is not a default
                if self._default_or_none is None:
                    return None

                return copy.deepcopy(self._default_or_none)

        return new_value

    def same_value(self, first_value, second_value) -> bool:
        derived_value = self.apply_derivation(first_value)
        if derived_value is None:
            return False
        return derived_value == second_value

    def result(self):
        return PrometheusDerivedLabelResult(self)


class PrometheusMetric(PrometheusNode):
    """
    Stores a Prometheus metric within a node.
    """

    def __init__(self, querier: PrometheusQuerier, datasource_name: str, metric_name: str):
        super().__init__(querier, datasource_name, metric_name)
        self._querier = querier

    def typeof(self):
        return float

    def metric_name(self):
        return self.name()

    def canonical_label_name(self):
        return self.metric_name()

    def label_matches(self) -> typing.Tuple[str, ...]:
        return (
            '__name__="{}"'.format(self.metric_name()),
        )

    def result(self):
        return PrometheusMetricResult(self)


class PrometheusEnumMetric(PrometheusMetric):
    """
    A fake metric that wraps around a label with enumerable/fixed values
    and a metric to present a single metric whose values come from the wrapped
    metric values where the particular label value applies.

    e.g. one might have a metric called 'pdu_measurements', which returns
         various measurements about power the PDU collects (from SNMP). Which
         measurement you want depends on the value of a 'measurement_index'
         label. A value of 1 might mean humidity, a value of 2 might mean
         active power, etc.  Naturally, when you query things you don't want to
         specify the index since that is non-obvious what you're querying. This
         wrapper node presents these metrics such as humidity as a node that
         behind the scenes queries with a particular measurement_index value
         so the index label does not appear in the graph.
    """

    def __init__(self, querier: PrometheusQuerier, datasource_name: str,
                 target_metric_name: str, new_metric_name: str,
                 enumerated_label_name: str, fixed_label_value: typing.Any):
        super().__init__(querier, datasource_name, new_metric_name)
        self._target_metric_name = target_metric_name
        self._enumerated_label_name = enumerated_label_name
        self._fixed_label_value = fixed_label_value

    def metric_name(self):
        return self._target_metric_name

    def enumerated_label_name(self):
        return self._enumerated_label_name

    def fixed_label_value(self):
        return self._fixed_label_value

    def canonical_label_name(self):
        return self.enumerated_label_name()

    def label_matches(self) -> typing.Tuple[str, ...]:
        return super().label_matches() + (
            '{}="{}"'.format(self.enumerated_label_name(), self.fixed_label_value()),
        )

    def result(self):
        # No need for a special metric enum result class, since we provide
        # an appropriate match in label_matches() that should do the filtering
        # we want
        return PrometheusMetricResult(self)


LabelValues = typing.Tuple[typing.Dict[str, str], typing.Any]


class PrometheusResult(datagraph.Result, abc.ABC):
    """
    An abstract result for Prometheus nodes.

    Subclasses should implement _query_values(). join() is provided, but relies
    on the constructor signature remaining the same as this class (in terms of
    positional arguments).
    """

    def __init__(self, node: PrometheusNode,
                 prev_result: typing.Optional['PrometheusResult'] = None):
        super().__init__(node)
        self._prev_result = prev_result
        self._cached_values = None

    def join(self, other_node: datagraph.DataNode) -> datagraph.Result:
        node = self.node()
        assert isinstance(node, PrometheusNode)
        if isinstance(other_node, PrometheusNode) and other_node.datasource_name() == node.datasource_name():
            # This is a hacky way to return PrometheusLabelResult for when
            # other_node is a PrometheusLabel, and a PrometheusMetricResult
            # for when other_node is a PrometheusMetric, etc...
            #
            # This works because all Prometheus*Result classes have the same
            # constructor parameter signature via the base PrometheusResult
            result_constructor = type(other_node.result())
            return result_constructor(other_node, self)
        else:
            # return other_node.result()
            assert False

    def _comparable_node_values(self, ancestor_node_values: datagraph.NodeValues) \
            -> typing.Dict[typing.Tuple[PrometheusNode, str], typing.Any]:
        node = self.node()
        assert isinstance(node, PrometheusNode)

        node_values = {}
        for ancestor_node, expected_value in ancestor_node_values.items():
            if (isinstance(ancestor_node, PrometheusNode)
                    and ancestor_node.datasource_name() == node.datasource_name()):
                node_values[(ancestor_node, ancestor_node.canonical_label_name())] = expected_value

        return node_values

    def _joined_label_matches(self) -> typing.Iterable[str]:
        if self._prev_result:
            yield from self._prev_result._joined_label_matches()

        node = self.node()
        assert isinstance(node, PrometheusNode)
        yield from node.label_matches()

    def as_query(self):
        # set -> deduplicate when joined labels are derived
        # ordered -> make order consistent (easier for grepping logs)
        return "{{{}}}".format(", ".join(sorted(set(self._joined_label_matches()))))

    @abc.abstractmethod
    def _raw_values(self) -> typing.Iterable[LabelValues]:
        raise NotImplementedError()

    def raw_values(self) -> typing.List[LabelValues]:
        if not self._cached_values:
            # list -> if iterable keep around
            self._cached_values = list(self._raw_values())

        return self._cached_values.copy()

    def raw_filtered_values(self, ancestor_node_values: datagraph.NodeValues) \
            -> typing.Iterator[LabelValues]:
        comparable_label_values = self._comparable_node_values(ancestor_node_values)

        for label_dict, value in self.raw_values():
            for label_and_name, expected_value in comparable_label_values.items():
                label, label_name = label_and_name
                if label_name in label_dict and not label.same_value(label_dict[label_name], expected_value):
                    break
            else:
                yield label_dict, value

    def duplicated_values(self, ancestor_node_values: typing.Optional[datagraph.NodeValues] = None):
        if not ancestor_node_values:
            ancestor_node_values = {}

        for _, value in self.raw_filtered_values(ancestor_node_values):
            yield self.node().typeof()(value)

    def values(self, ancestor_node_values: typing.Optional[datagraph.NodeValues] = None) -> typing.Iterable[typing.Any]:
        return more_itertools.unique_everseen(self.duplicated_values(ancestor_node_values))


class PrometheusLabelResult(PrometheusResult):

    def __init__(self, label_node: PrometheusLabel, prev_result: typing.Optional['PrometheusLabelResult'] = None):
        super().__init__(label_node, prev_result)

    def _raw_values(self) -> typing.Iterable[LabelValues]:
        node = self.node()
        assert isinstance(node, PrometheusLabel)

        # The HTTP /label/<label>/values API works for only one label;
        # more efficient
        label_matches = list(self._joined_label_matches())
        if len(label_matches) <= 1:
            for label_value in node.querier().label_values(node.canonical_label_name()):
                yield {node.canonical_label_name(): label_value}, label_value

        else:
            for label_dict, _ in node.querier().query(self.as_query()):
                yield label_dict, label_dict[node.canonical_label_name()]


class PrometheusDerivedLabelResult(PrometheusLabelResult):

    def __init__(self, derived_label_node: PrometheusDerivedLabel,
                 prev_result: typing.Optional['PrometheusLabelResult'] = None):
        super().__init__(derived_label_node, prev_result)

    def duplicated_values(self, ancestor_node_values: typing.Optional[datagraph.NodeValues] = None) \
            -> typing.Iterable[typing.Any]:
        if not ancestor_node_values:
            ancestor_node_values = {}

        node = self.node()
        assert isinstance(node, PrometheusDerivedLabel)

        derived_values = []
        for raw_value in super().duplicated_values(ancestor_node_values):
            maybe_value = node.apply_derivation(raw_value)
            if maybe_value is not None:  # derivation may not work out
                derived_values.append(maybe_value)

        # Combine values that are the same, regardless of input order; We
        # could try and combine similar values that are next to each other
        # without sorting, but the problem is that the _values() we get have
        # no order with respect to the derivation, so combining values next to
        # each other wouldn't work (or at least isn't guaranteed to work)

        # groupby returns an iterable of tuples, where the first item is the key
        # and the second item is the group of values
        for value, _ in itertools.groupby(sorted(derived_values)):
            yield value


class PrometheusMetricResult(PrometheusResult):

    def __init__(self, metric: PrometheusMetric, prev_result: typing.Optional[PrometheusLabelResult] = None):
        super().__init__(metric, prev_result)

    def join(self, other_node: datagraph.DataNode):
        raise ValueError("Cannot join on a metric result ({})!".format(self.node().metric_name()))

    def _raw_values(self) -> typing.Iterable[LabelValues]:
        yield from self.node().querier().query(self.as_query())


@dataclasses.dataclass(frozen=True)
class PrometheusLabelDerivation:
    target_label_name: str
    new_label_name: str
    parent_label_name: typing.Optional[str]
    derivation_funcs: typing.List[DerivationFunc]
    default_or_none: typing.Optional[str]


@dataclasses.dataclass(frozen=True)
class PrometheusMetricRelationship:
    name: str
    primary_label_names: typing.List[str]
    label_name_aliases: typing.Set[typing.Tuple[str]]
    value_label_names: typing.List[str]
    label_value_enums: typing.Dict[str, typing.Dict[str, str]]

    def has_same_labels(self, other: 'PrometheusMetricRelationship'):
        return (
            self.primary_label_names == other.primary_label_names
            and self.label_name_aliases == other.label_name_aliases
            and self.value_label_names == other.value_label_names
            and self.label_value_enums == other.label_value_enums
        )


def create_graph_from_relationships(querier: PrometheusQuerier,
                                    datasource_name: str,
                                    metric_relationships: typing.List[PrometheusMetricRelationship],
                                    label_categories: typing.Dict[str, typing.List[str]],
                                    label_derivations: typing.List[PrometheusLabelDerivation]):
    graph = PrometheusDataGraph(querier, datasource_name)
    label_derivations_map = {derivation.new_label_name: derivation for derivation in label_derivations}

    def construct_label(label_name, prev_label_node):
        if label_name in label_derivations_map:
            derivation = label_derivations_map[label_name]
            return graph.construct_derived_prometheus_label(derivation, prev_label_node)
        return graph.construct_prometheus_label(label_name, prev_label_node)

    for metric_relationship in metric_relationships:
        primary_label_names = metric_relationship.primary_label_names
        prev_primary_label_node = None
        for primary_label_name in primary_label_names:
            assert primary_label_name not in metric_relationship.label_value_enums
            prev_primary_label_node = construct_label(primary_label_name, prev_primary_label_node)

        # Create alias label nodes initially to allow for derived labels to refer
        # to them, but delay fully setting up edges until after the metric is
        # constructed, so that aliases all point to metrics if needed.
        alias_label_names = more_itertools.flatten(metric_relationship.label_name_aliases)
        for alias_label_name in more_itertools.unique_everseen(alias_label_names):
            construct_label(alias_label_name, None)

        assert prev_primary_label_node is not None
        for value_label_name in metric_relationship.value_label_names:
            assert value_label_name != metric_relationship.name  # common mistake
            assert value_label_name not in metric_relationship.primary_label_names
            assert value_label_name not in metric_relationship.label_value_enums
            construct_label(value_label_name, prev_primary_label_node)

        for original_label_name, label_values_to_new_name in metric_relationship.label_value_enums.items():
            for fixed_label_value, new_label_name in label_values_to_new_name.items():
                graph.construct_prometheus_enum_metric(
                    original_metric_name=metric_relationship.name,
                    new_metric_name=new_label_name,
                    enumerated_label_name=original_label_name,
                    fixed_value=fixed_label_value,
                    from_label_node=prev_primary_label_node
                )

        graph.construct_prometheus_metric(metric_relationship.name, prev_primary_label_node)

        for label_name_alias_group in metric_relationship.label_name_aliases:
            graph.construct_prometheus_label_aliases(set(label_name_alias_group))

    for category_label_name, subset_label_names in label_categories.items():
        category_label_node = graph.construct_prometheus_label(category_label_name)
        for subset_label_name in subset_label_names:
            graph.add_edge_node(category_label_node, graph.find_by_label_name(subset_label_name))

    return graph


def format_yaml(querier: PrometheusQuerier,
                metric_relationships: typing.List[PrometheusMetricRelationship],
                label_categories: typing.Dict[str, typing.List[str]]) -> str:
    # Group metrics where their labels (and associated enums and the like)
    # are the same
    counter = 1
    grouped_relationships = collections.defaultdict(list)
    for metric_relationship in metric_relationships:
        name = metric_relationship.name
        prefix = name.rsplit("_", maxsplit=1)[0] if "_" in name else name
        for group_prefix, relationships in grouped_relationships.copy().items():
            if relationships[0].has_same_labels(metric_relationship):
                grouped_relationships[group_prefix].append(metric_relationship)
                break
        else:
            if prefix in grouped_relationships:  # name collision
                prefix += str(counter)
                counter += 1

            grouped_relationships[prefix].append(metric_relationship)

    # See from_yaml for the format here
    datasource_data = {
        "datasource": "prometheus",
        "target": querier.target(),
        "proxy": querier.proxy(),
        "label_categories": {
            category: list(refinement_labels)
            for category, refinement_labels in label_categories.items()
        },
        "groups": {
            prefix: {
                "metrics": [m.name for m in metric_relationships],
                "alias_labels": [list(alias_group) for alias_group in metric_relationships[0].label_name_aliases],
                "primary_labels": list(metric_relationships[0].primary_label_names),
                "value_labels": list(metric_relationships[0].value_label_names),
                "label_value_enums": metric_relationships[0].label_value_enums
            }
            for prefix, metric_relationships in grouped_relationships.items()
        }
    }
    return datagraph.dump_yaml("prometheus", datasource_data)


def node_name_from_yaml_identifier(yaml_identifier: str) -> str:
    # labels/metric names are currently directly mapped into the graph
    return yaml_identifier


def _match_or_empty(pattern: str, string: str):
    match_or_none = re.search(pattern, string)
    if match_or_none is None:
        raise ValueError("Unable to match {} against pattern '{}'".format(string, pattern))
    return match_or_none.group(1)


def _derivation_from_yaml(derived_labels_data: typing.List[typing.Dict[str, str]]) \
        -> typing.List[PrometheusLabelDerivation]:
    """
    Returns a list of prometheus derivations found in the given YAML data.

    e.g.
    derived_labels:
      # tempSensorName="U5 Cold Bottom" (u is row, 5 is rack, cold is aisle)
      - tempSensorName: row
        regex: "([a-zA-Z])0*[0-9]+ .*"
        func: tolower
        default: A1

    >>> data = {"tempSensorName": "row",
                "regex": "([a-zA-Z])0*[0-9]+ .*",
                "func": "tolower"}
    >>> _derivation_from_yaml([data])
    [PrometheusLabelDerivation(
        target_label_name="tempSensorName"
        new_label_name="row"
        derivation_funcs=[<func _match_or_empty...>, <method 'tolower' of 'str' objects>]
     )]
    """
    derivation_keywords = {"func", "funcs", "regex", "parent", "default"}
    derivations = []

    for derive_dict in derived_labels_data:
        non_keyword_mappings = []
        keyword_mappings = []
        for key, value in derive_dict.items():
            if key not in derivation_keywords:
                non_keyword_mappings.append((key, value))
            else:
                keyword_mappings.append((key, value))

        if len(non_keyword_mappings) != 1:
            raise ValueError("Expected only one mapping between a label "
                             "name and a new derived label name")

        parent_label_name = None
        from_label_name, to_label_name = non_keyword_mappings[0]
        derive_funcs = []
        default_or_none = None
        for derivation_type, derivation_data in keyword_mappings:
            if derivation_type == "regex":
                # Here, we basically create a wrapper function around _match_or_empty
                # that automagically provides derivation data (the regexp) to
                # _match_or_empty so that the user of the function only needs to
                # provide the value (derivations are str -> str funcs).
                #
                # A lambda such as:
                # lambda label_value: _match_or_empty(derivation_data, label_value)
                #
                # might appear to do the same thing, but due to Python's lexical capture
                # of variables (https://stackoverflow.com/questions/2295290/what-do-lambda-function-closures-capture)
                # this results in last derivation_data value within this loop being
                # provided to the function when it is finally called.
                # functools.partial() fixes this for us.
                derive_funcs.append(functools.partial(_match_or_empty, derivation_data))

            elif derivation_type == "parent":
                parent_label_name = derivation_data

            elif derivation_type == "func" or derivation_type == "funcs":
                uneval_data_list = [derivation_data] if derivation_type == "func" else derivation_data
                for uneval_data in uneval_data_list:
                    try:
                        derive_funcs.append(eval(uneval_data))
                    except Exception as err:
                        raise ValueError("Could not evaluate expression '{}': {}"
                                         .format(uneval_data, err))
            elif derivation_type == "default":
                default_or_none = derivation_data
            else:
                assert False

        derivation = PrometheusLabelDerivation(
            from_label_name,
            to_label_name,
            parent_label_name,
            derive_funcs,
            default_or_none
        )
        derivations.append(derivation)

    return derivations


def from_yaml(datasource_name: str,
              datasource_data: dict,
              cache: typing.Optional[acache.AbstractCache] = None):
    #  datasource: prometheus
    #  target: localhost:9090
    #  label_categories:
    #    group: [instance]
    #  metrics:
    #    interface: [ifHCOutOctets]
    #      primary_labels: [instance, ifIndex]
    #      alias_labels:
    #        - [ifIndex, ifName]
    #      value_labels:
    #        - ifAlias
    #
    # results in:
    # {'datasource': 'prometheus',
    #  'label_categories': {'group': ['instance']},
    #  'metrics': {'ifHCOutOctets': {'alias_labels': [['ifIndex', 'ifName'],],
    #                                'primary_labels': ['instance',
    #                                                   'ifIndex'],
    #                                'derived_labels': [{'ifIndex': 'if_type',
    #                                                    'regex': '([a-zA-Z])[0-9]+'}]  # e.g. eth of eth0
    #                                                    'func': 'tolower'}]
    #                                'value_labels': ['ifAlias']}}}}}
    assert datasource_data["datasource"] == "prometheus"

    target = datasource_data["target"]
    proxy_or_none = datasource_data.get("proxy", None)
    querier = PrometheusQuerier(target, proxy=proxy_or_none, cache=cache)

    categories = datasource_data.get("label_categories", {})
    derivations = _derivation_from_yaml(datasource_data.get("derived_labels", []))
    relationships = []
    for metric_group_name, metric_data in datasource_data["groups"].items():
        assert len(metric_data["metrics"]) > 0

        for metric_name in metric_data["metrics"]:
            relationship = PrometheusMetricRelationship(
                metric_name,
                metric_data["primary_labels"],
                metric_data.get("alias_labels", {}),
                [
                    value_label_name
                    for value_label_name in metric_data.get("value_labels", {})
                    if value_label_name != metric_name
                ],
                metric_data.get("label_value_enums", {}),
            )
            relationships.append(relationship)

    return create_graph_from_relationships(querier, datasource_name, relationships, categories, derivations)
