# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Defines a PCP-PMAPI data source according to datagraph.py.
"""

from __future__ import annotations
import copy
from pydoc import locate
import collections
import dataclasses
import json
import typing

import requests
import yaml

from .. import core
from .. import datagraph


def mangle_metric_name(metric: str) -> str:
    assert "-" not in metric
    return metric.replace(".", "-")


def demangle_metric_name(mangled: str) -> str:
    return ".".join(mangled.split("-"))


@dataclasses.dataclass(frozen=True)
class InDom:
    name: str
    indom_str: str

    def path(self) -> core.Path:
        return core.Path("." + self.indom_str)

    def is_parent_of(self, indom: InDom) -> bool:
        return indom.path().is_child_of(self.path())


@dataclasses.dataclass(frozen=True)
class Metric:
    name: str
    indom_str: typing.Optional[str]
    type: typing.Type

    def has_indom(self) -> bool:
        return self.indom_str is not None


InstanceValues = typing.Dict[int, typing.Any]
InstanceMap = typing.Dict[int, str]


class PMProxyQuerier:

    def __init__(self, target: str, proxy: typing.Optional[str] = None):
        self._target = target
        self._proxy = proxy

    def target(self):
        return self._target

    def proxy(self):
        return self._proxy

    def indom(self, indom_str) -> InDom:
        resp = requests.get(
            "http://{}/pmapi/indom".format(self._target),
            params={"indom": indom_str},
            proxies=self._proxy
        )

        json_data = resp.json()

        # Here we try and pick a label, going with the cannoncial 'indom_name',
        # if it exists, then falling back to a terrible but usable alternative.
        # Note that we cannot really be clever here since these need to be
        # unique!
        label_data = json_data.get("label", {})
        if "indom_name" in label_data:
            # typically named 'per ...'; try and extract the '...', but beware
            # of 'per ...' like 'per zone per numa_node'
            per_targets = label_data["indom_name"].split("per")[1:]
            if len(per_targets) >= 1:
                indom_name = "_".join(per_targets)  # e.g. zone_numa_node
                return InDom(indom_name, indom_str)
            # ~fallthrough~

        if "text-oneline" in json_data:
            # Best we can do; terrible for data like:
            # 'pressure time averages for 10 seconds, 1 minute and 5 minutes'
            replacements = {
                " ": "_",
                ".": "_",
                "-": "_",
                "(": "",
                ")": "",
                '"': "",
                "'": "",
                ",": "",
            }
            indom_name = json_data["text-oneline"]
            for original, replacement in replacements.items():
                indom_name = indom_name.replace(original, replacement)
            return InDom(indom_name, indom_str)

        raise ValueError("Could not find suitable name for InDom, within data: " + str(json_data))

    def metrics(self, metric_names: typing.Optional[typing.Set[str]]) -> typing.List[Metric]:
        params = {}
        if metric_names:
            params = {"names": ",".join(metric_names)}

        resp = requests.get(
            "http://{}/pmapi/metric".format(self._target),
            params=params,
            proxies=self._proxy
        )

        metrics = []
        metrics_data = resp.json()["metrics"]
        for metric_data in metrics_data:
            metric = Metric(metric_data["name"], metric_data.get("indom", None), type_from_typename(metric_data["type"]))
            metrics.append(metric)

        return metrics

    def indom_instances(self, indom_str: str) -> InstanceMap:
        resp = requests.get(
            "http://{}/pmapi/indom".format(self._target),
            params={"indom": indom_str},
            proxies=self._proxy
        )

        instance_map = {}
        instance_dict_list = resp.json()["instances"]
        for instance_dict in instance_dict_list:
            instance = instance_dict["instance"]
            instance_name = instance_dict["name"]
            instance_map[instance] = instance_name

        return instance_map

    def metric_values(self, metric_name: str, instances: typing.Optional[InstanceMap] = None) -> InstanceValues:
        resp = requests.get(
            "http://{}/pmapi/fetch".format(self._target),
            params={"name": metric_name},
            proxies=self._proxy
        )

        instance_values = {}
        data = resp.json()
        # 0 -> only one name requested
        instance_dict_list = data["values"][0]["instances"]
        for instance_dict in instance_dict_list:
            instance = instance_dict["instance"]
            if not instances or instance in instances:
                value = instance_dict["value"]
                instance_values[instance] = value

        return instance_values


class PCPDataGraph(datagraph.DataGraph):

    def __init__(self, querier: PMProxyQuerier, datasource_name: str):
        super().__init__()
        self._querier = querier
        self._datasource_name = datasource_name

    def _create_indom_node(self, indom: InDom):
        return InDomNode(
            self._querier,
            self._datasource_name,
            indom,
        )

    def construct_indom_node(self, indom: InDom):
        parent_node = None
        for node in self.nodes():
            if isinstance(node, InDomNode) and node.indom().is_parent_of(indom):
                parent_node = node

        indom_node = self._create_indom_node(indom)
        if parent_node:
            self.add_node(indom_node, parent_node)
        else:
            self.add_node(indom_node)

        return indom_node

    def _create_metric_node(self, metric: Metric):
        return MetricNode(
            self._querier,
            self._datasource_name,
            metric,
        )

    def construct_metric_node(self, metric: Metric, parent_indom_node: typing.Optional[InDomNode] = None):
        node = self._create_metric_node(metric)
        if parent_indom_node:
            self.add_node(node, parent_indom_node)
        else:
            self.add_node(node)

        return node


class InDomNode(datagraph.DataNode):

    def __init__(self, querier: PMProxyQuerier, datasource_name: str, indom: InDom):
        super().__init__(datasource_name, indom.name, str)
        self._querier = querier
        self._indom = indom

    def indom(self) -> InDom:
        return self._indom

    def indom_name(self) -> str:
        return self.name()

    def indom_str(self) -> str:
        return self._indom.indom_str

    def is_indom_for_metric(self, metric_node: MetricNode):
        return metric_node.metric().indom_str == self.indom_str()

    def querier(self) -> PMProxyQuerier:
        return self._querier

    def result(self) -> InDomResult:
        return InDomResult(self, self.querier().indom_instances(self.indom().indom_str))


class MetricNode(datagraph.DataNode):

    def __init__(self, querier: PMProxyQuerier, datasource_name: str, metric: Metric):
        super().__init__(datasource_name, mangle_metric_name(metric.name), metric.type)
        self._querier = querier
        self._metric = metric

    def metric(self) -> Metric:
        return self._metric

    def metric_name(self) -> str:
        return demangle_metric_name(self.name())

    def querier(self) -> PMProxyQuerier:
        return self._querier

    def result(self) -> MetricResult:
        return MetricResult(self, self.querier().metric_values(self.metric_name()), None)


class InDomResult(datagraph.Result):

    def __init__(self, indom_node: InDomNode, instances: InstanceMap):
        super().__init__(indom_node)
        self._instances = instances

    def join(self, other_node: datagraph.DataNode) -> datagraph.Result:
        node = self.node()
        assert isinstance(node, InDomNode)

        assert not isinstance(other_node, InDomNode)

        if isinstance(other_node, MetricNode) and other_node.datasource_name() == node.datasource_name():
            per_instance_values = node.querier().metric_values(other_node.metric_name(), instances=self._instances)
            return MetricResult(other_node, per_instance_values, copy.deepcopy(self._instances))

        return other_node.result()

    def values(self, ancestor_node_values: typing.Optional[datagraph.NodeValues] = None) \
            -> typing.Iterable[typing.Any]:
        if not ancestor_node_values:
            ancestor_node_values = {}

        node = self.node()
        assert isinstance(node, InDomNode)
        if node in ancestor_node_values:
            yield ancestor_node_values[node]
        else:
            yield from self._instances.keys()


class MetricResult(datagraph.Result):

    def __init__(self, metric_node: MetricNode, per_instance_values: InstanceValues, instances: typing.Optional[InstanceMap]):
        super().__init__(metric_node)
        self._per_instance_values = per_instance_values
        self._instances = instances

    def join(self, other_node: datagraph.DataNode) -> datagraph.Result:
        node = self.node()
        assert isinstance(node, MetricResult)

        assert not isinstance(other_node, InDomNode)
        assert not isinstance(other_node, MetricNode)

        return other_node.result()

    def values(self, ancestor_node_values: typing.Optional[datagraph.NodeValues] = None) \
            -> typing.Iterable[typing.Any]:
        if not ancestor_node_values:
            ancestor_node_values = {}

        node = self.node()
        assert isinstance(node, MetricNode)

        for instance, value in self._per_instance_values.items():
            for ancestor_node, expected_value in ancestor_node_values.items():
                if (isinstance(ancestor_node, InDomNode)
                        and ancestor_node.is_indom_for_metric(node)
                        and instance != expected_value):
                    break
            else:
                yield value


def create_graph_from_metrics(querier: PMProxyQuerier,
                              datasource_name: str,
                              metrics: typing.List[Metric],
                              indoms: typing.Set[InDom]):
    graph = PCPDataGraph(querier, datasource_name)

    indom_str_to_node_map: typing.Dict[str, InDomNode] = {}
    for indom in indoms:
        indom_str_to_node_map[indom.indom_str] = graph.construct_indom_node(indom)

    for metric in metrics:
        if metric.has_indom():
            indom_node = indom_str_to_node_map[metric.indom_str]  # type: ignore
            graph.construct_metric_node(metric, indom_node)
        else:
            graph.construct_metric_node(metric)

    return graph


def node_name_from_yaml_identifier(yaml_identifier: str) -> str:
    # YAML metrics are referred to using PCP notation (category.metric)
    return mangle_metric_name(yaml_identifier)


def mangle_yaml_identifier(metric_name: str):
    return metric_name.replace(".", "_")


def type_from_typename(typename: str) -> typing.Type:
    # curl -s 'http://localhost:44322/pmapi/metric' | jq | grep \"type | sort | uniq | awk -F\" '{ print $4 }'
    hardcoded_conversions = {
        "32": int,
        "64": int,
        "double": float,
        "string": str,
        "u32": int,
        "u64": int,
    }
    if typename in hardcoded_conversions:
        return hardcoded_conversions[typename]

    # fallback to locate(), which returns a type from a fully qualified type
    # name (e.g. '__main__.Object' with 'class Object' -> Object): 'int' -> int
    maybe_type = locate(typename)
    if not maybe_type:
        # maybe in our scope? e.g. __main__?
        maybe_type = locate(__name__ + "." + typename)
        if not maybe_type:
            raise ValueError("Could not find Python type for " + typename)

    return maybe_type


def type_to_typename(typeof: typing.Type) -> str:
    return typeof.__name__


def format_yaml(querier: PMProxyQuerier, metrics: typing.List[Metric],
                indoms: typing.Set[InDom]) -> str:
    # See from_yaml for the format here
    groups = {}
    for metric in metrics:
        group_data = {
            "metrics": [metric.name],
            "type": type_to_typename(metric.type),
        }
        if metric.indom_str:
            group_data["indom"] = metric.indom_str

        groups[mangle_yaml_identifier(metric.name)] = group_data

    datasource_data = {
        "datasource": "pcp",
        "target": querier.target(),
        "indoms": {
            indom.name: indom.indom_str
            for indom in indoms
        },
        "groups": groups
    }

    proxy_or_none = querier.proxy()
    if proxy_or_none:
        datasource_data["proxy"] = proxy_or_none

    return datagraph.dump_yaml("pcp", datasource_data)


def from_yaml(datasource_name, datasource_data, cache):
    """
    datasource: pcp
    target: localhost:44322
    indoms:
      cpu: "60.0"
      disk: "60.1"
    groups:
      diskdev:
        metrics: [disk.dev.read, disk.dev.write]
        type: int
        indom: "60.1"
      mem:
        metrics: [mem.physmem, mem.freemem]
        type: int
      cpu:
        metrics: [kernel.percpu.cpu.user, kernel.percpu.cpu.nice]
        indom: "60.0"
        type: int
    """
    assert datasource_data["datasource"] == "pcp"

    target = datasource_data["target"]
    proxy_or_none = datasource_data.get("proxy", None)
    querier = PMProxyQuerier(target, proxy=proxy_or_none)

    indom_strs_to_indom_map = {}
    for indom_name, indom_float in datasource_data["indoms"].items():
        # str -> '60.1' is interpreted as a float in YAML
        indom_str = str(indom_float)
        assert indom_str not in indom_strs_to_indom_map
        indom_strs_to_indom_map[indom_str] = InDom(indom_name, indom_str)

    metrics = []
    for metric_group_name, metric_data in datasource_data["groups"].items():
        assert len(metric_data["metrics"]) > 0
        indom_or_none = None
        if "indom" in metric_data:
            indom_or_none = str(metric_data["indom"])
            assert indom_or_none in indom_strs_to_indom_map

        for metric_name in metric_data["metrics"]:
            typeof = type_from_typename(metric_data["type"])
            metric = Metric(metric_name, indom_or_none, typeof)
            metrics.append(metric)

    return create_graph_from_metrics(querier, datasource_name, metrics, set(indom_strs_to_indom_map.values()))
