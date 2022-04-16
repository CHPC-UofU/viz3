# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Defines the data graph model and conversions to and from YAML.
"""

from __future__ import annotations
import abc
import functools
import os
import types
import typing
import yaml

from .. import core
from .. import acache

from matplotlib import pyplot as plt
import networkx


def mangle_name(datasource_name, node_name) -> str:
    assert node_name != ""
    assert ":" not in datasource_name and ":" not in node_name
    return datasource_name + ":" + node_name


def demangle_name(mangled_name) -> typing.Tuple[str, str]:
    return mangled_name.split(":")


class DataGraph:
    """
    An abstract directed acyclic graph of nodes, where each node represents a
    data type, and the directed connection between nodes represent a one to
    many relationship within the data. A connection between nodes does not
    imply any type of mapping between the data (not necessarily bijection,
    injective, surjective).

    Thus, a path through the graph to a end node can be thought of a refinement
    of that end node's data, based on the one-to-many mappings of intermediate
    nodes.

    Each node in the graph is a subclass of DataNode.
    """

    def __init__(self):
        self._network = networkx.DiGraph()
        self._adaptors = {}

    @staticmethod
    def combine_subgraphs(all_graphs: typing.List[DataGraph]):
        """
        Combines the given data graphs together into a single graph.
        """
        combined_network = networkx.compose_all([graph._network for graph in all_graphs])
        new_datagraph = DataGraph()
        new_datagraph._network = combined_network
        for graph in all_graphs:
            for key, adaptor in graph._adaptors.items():
                assert key not in new_datagraph._adaptors
                new_datagraph._adaptors[key] = adaptor

        return new_datagraph

    def draw(self):
        """
        Draws a graph using networkx and matplotlib.
        """
        networkx.drawing.draw_networkx(self._network, with_labels=True)
        plt.show()

    def write_dot(self, to_file: str):
        """
        Writes the graph out to the given DOT file.
        """
        networkx.drawing.nx_pydot.write_dot(self._network, to_file)

    def _assert_no_cycles_after_add(self, node: DataNode):
        cycles_iter = networkx.simple_cycles(self._network)
        try:
            cycle = next(cycles_iter)
            self.draw()
            raise ValueError("A cycle (path: {}) was found in the data graph "
                             "after adding {}!".format(cycle, node.mangled_name()))
        except StopIteration:
            pass

    def add_edge_node(self, node: DataNode, to_node: DataNode):
        self._network.add_edge(node, to_node)
        self._assert_no_cycles_after_add(node)

    def add_intermediate_node(self, node: DataNode, to_node: DataNode):
        assert to_node in self._network
        for in_edge_node, _ in self._network.copy().in_edges(to_node):
            self._network.remove_edge(in_edge_node, to_node)
            self._network.add_edge(in_edge_node, node)

        self._network.add_edge(node, to_node)
        self._assert_no_cycles_after_add(node)

    def add_node(self, node: DataNode, from_node: typing.Optional[DataNode] = None):
        if not from_node:
            self._network.add_node(node)
        else:
            self._network.add_edge(from_node, node)
        self._assert_no_cycles_after_add(node)

    def add_node_next_to(self, node: DataNode, next_to_node: DataNode):
        assert next_to_node in self._network
        for in_edge_node, _ in self._network.in_edges(next_to_node):
            self._network.add_edge(in_edge_node, node)

        for _, out_edge_node in self._network.out_edges(next_to_node):
            self._network.add_edge(node, out_edge_node)

        self._assert_no_cycles_after_add(node)

    @functools.lru_cache
    def resolve_shortest_paths_within(self, partial_path: core.Path) -> core.Path:
        if not partial_path:
            return partial_path

        first, rest_path = partial_path.first(), partial_path.without_first()
        try:
            return core.Path() + first + self._resolve_shortest_path(rest_path, self.find_with_mangled_name(first))
        except ValueError as err:
            raise ValueError("Failed to resolve shortest path within {}: {}".format(partial_path, err))

    def _resolve_shortest_path(self, partial_path: core.Path, prev_node: DataNode) -> core.Path:
        if partial_path.empty():
            return partial_path

        node = self.find_with_mangled_name(partial_path.first())
        try:
            shortest_path = sorted(self.paths_between(node, prev_node))[0]
        except IndexError:
            raise ValueError("No path between {} and {} in {}".format(prev_node.mangled_name(), node.mangled_name(), partial_path))
        return shortest_path.without_first() + self._resolve_shortest_path(partial_path.without_first(), node)

    @functools.lru_cache
    def paths_between(self, node: DataNode, ancestor_node: DataNode) -> core.Path:
        original_node = node
        path = core.Path()
        paths = []
        queue = [(ancestor_node, node, path)]
        while queue:
            start_node, end_node, path = queue.pop()

            path += start_node.mangled_name()
            if start_node == end_node:
                paths.append(path)
            for node in set(self._network[start_node]).difference(set(path.parts())):
                queue.append((node, end_node, path))

        if not paths:
            raise ValueError("No path exists between {} and {}".format(ancestor_node, original_node))

        return paths

    def add_leaf(self, leaf_node: DataNode, owning_node: DataNode):
        self._network.add_edge(owning_node, leaf_node)

    def is_predecessor(self, node, supposed_predecessor_node, including=False) -> bool:
        return (
            self._network.has_predecessor(supposed_predecessor_node, node)
            or (including and node == supposed_predecessor_node)
        )

    def is_successor(self, node, supposed_successor_node, including=False) -> bool:
        return (
                self._network.has_successor(supposed_successor_node, node)
                or (including and node == supposed_successor_node)
        )

    @functools.lru_cache
    def find(self, datasource_name, name) -> 'DataNode':
        """
        Returns a node with the corresponding name and datasource, raising
        ValueError if no such node exists.
        """
        for node in self._network.nodes():
            if node.datasource_name() == datasource_name and node.name() == name:
                return node
        raise ValueError("No such name {}, with datasource {}, in network {} ([])".format(
            name,
            datasource_name,
            str(self._network),
            list(map(lambda n: n.mangled_name(), self._network.nodes())))
        )

    def find_with_mangled_name(self, mangled_name):
        datasource_name, name = demangle_name(mangled_name)
        return self.find(datasource_name, name)

    def nodes(self) -> typing.List[DataNode]:
        return [
            node
            for node in self._network.nodes()
            if isinstance(node, DataNode)
        ]

    def successors_of(self, node: DataNode) -> typing.List[DataNode]:
        return [
            suc_node
            for suc_node in self._network.successors(node)
            if isinstance(suc_node, DataNode)
        ]

    def leaves(self) -> typing.List[DataNode]:
        return [
            node
            for node in self._network.nodes()
            if len(list(self._network.successors(node))) == 0
        ]

    def successor_leaves_of(self, node: DataNode) -> typing.List[DataNode]:
        return [
            suc_node
            for suc_node in self._network.successors(node)
            if len(list(self._network.successors(suc_node))) == 0
        ]

    def has_adaptor(self, from_node: DataNode, to_node: DataNode) -> bool:
        return (from_node, to_node) in self._adaptors

    def adaptors_from(self, from_node: DataNode) -> typing.List[Adaptor]:
        adaptors = []
        for adaptor_from_and_to_nodes, adaptor in self._adaptors.items():
            adaptor_from_node, _ = adaptor_from_and_to_nodes
            if adaptor_from_node == from_node:
                adaptors.append(adaptor)
        return adaptors

    def adaptor(self, from_node: DataNode, to_node: DataNode) -> Adaptor:
        return self._adaptors[(from_node, to_node)]


class DataNode(abc.ABC):
    """
    Defines a node in the data graph. This class is meant to be subclasses by
    custom data sources.
    """

    def __init__(self, datasource_name: str, name: str, typeof: typing.Type):
        self._datasource_name = datasource_name
        self._name = name
        # We access this regularly; so cache it
        self._mangled_name = mangle_name(self._datasource_name, self._name)
        self._typeof = typeof

    def typeof(self) -> typing.Type:
        return self._typeof

    def datasource_name(self):
        return self._datasource_name

    def name(self) -> str:
        return self._name

    def mangled_name(self):
        return self._mangled_name

    def same_value(self, first_value, second_value) -> bool:
        return first_value == second_value

    def result(self) -> 'Result':
        raise NotImplementedError()

    def __hash__(self):
        return hash(self.mangled_name())

    def __eq__(self, other):
        if isinstance(other, DataNode):
            return self.mangled_name() == other.mangled_name()
        return False

    def __repr__(self):
        return "Node({}, type: {})".format(self.mangled_name(), str(self.typeof()))


class Adaptor(abc.ABC):
    """
    An adaptor adapts the nodes and values of one data node to another data
    node.
    """

    def applies_to(self, node: DataNode) -> bool:
        """
        Returns whether this adaptor adapts the node to some other node.
        """
        raise NotImplementedError()

    def adapt_node(self, from_node: DataNode) -> DataNode:
        """
        Adapts the node to a new node.
        """
        raise NotImplementedError()

    def adapt_value(self, value: typing.Any) -> typing.Any:
        """
        Adapts the value to a new value.
        """
        raise NotImplementedError()


class DirectionalNodeAdaptor(Adaptor):
    """
    Trivial adaptor that simply returns the same value.
    """

    def __init__(self, from_node: DataNode, to_node: DataNode):
        self._from_node = from_node
        self._to_node = to_node

    def applies_to(self, node: DataNode) -> bool:
        return node == self._from_node

    def adapt_node(self, node: DataNode):
        if node == self._from_node:
            return self._to_node
        raise ValueError("Node given ({}) does not apply to this adaptor! {} -> {}".format(node, self._from_node, self._to_node))

    def adapt_value(self, value: typing.Any) -> typing.Any:
        return self._to_node.typeof()(value)

    def __repr__(self):
        return "DirectionalNodeAdaptor({} -> {})".format(self._from_node, self._to_node)


class RelabelNodeAdaptor:

    def __init__(self, node1: DataNode, node2: DataNode, relabel_map: typing.Dict[str, str]):
        self._node1 = node1
        self._node2 = node2
        self._to_relabel_map = relabel_map
        self._from_relabel_map = {rhs: lhs for lhs, rhs in relabel_map.items()}

    def applies_to(self, node: DataNode):
        return self._node1 == node or self._node2 == node

    def adapt_node(self, node: DataNode):
        if node == self._node1:
            return self._node2
        elif node == self._node2:
            return self._node1
        raise ValueError("Node given ({}) does not apply to this adaptor! {} <-> {}".format(node, self._node1, self._node2))

    def adapt_value(self, value: typing.Any) -> typing.Any:
        if value in self._to_relabel_map:
            return self._to_relabel_map[value]
        if value in self._from_relabel_map:
            return self._from_relabel_map[value]
        assert False


NodeValues = typing.Dict['DataNode', typing.Any]


class Result(abc.ABC):

    def __init__(self, node):
        self._node = node

    def node(self) -> DataNode:
        return self._node

    def join(self, other_node: DataNode) -> Result:
        raise NotImplementedError()

    def values(self, ancestor_node_values: typing.Optional[NodeValues] = None) -> typing.Iterable[typing.Any]:
        raise NotImplementedError()

    def __hash__(self):
        return hash(self.node())

    def __eq__(self, other):
        if isinstance(other, Result):
            return hash(self) == hash(other)


class AdaptedResult(Result):
    """
    Wraps around the given result and adapts incoming results joined with
    a particular node so that they can be applied to the given result.

    This is primarily used to wrap around the result of data nodes that
    are allowed to be joined from a completely different data node result, such
    as when the results come from different datasource.

    e.g. a Result() from a fully-qualified domain name node (storing a bunch of
    fully qualified domain names) from a SQL database may want to be joined
    onto a result from a load avg node (storing 1m load averages of a bunch of
    nodes) from a Prometheus time-series database, whose ancestor node in the
    data graph is a shorthand hostname node from the same time-series database
    (the load averages are _differentiated_ from one another by shorthand hostnames).
    In order to facilitate a join between two different results, an adaptation
    from a fully qualified domain name to a shorthand hostname must be done. By
    wrapping the load average node in an AdaptedResult, the wrapper can
    translate the values of the FQDN node into shorthand hostnames, before
    calling the joining operation on the result with the new values.
    """

    def __init__(self, result: Result, adaptor: Adaptor):
        super().__init__(result.node())
        self._result = result
        self._adaptor = adaptor

    def node(self) -> DataNode:
        return self._result.node()

    def join(self, other_node: DataNode) -> Result:
        return self._result.join(other_node)

    def values(self, ancestor_node_values: typing.Optional[NodeValues] = None) -> typing.Iterable[typing.Any]:
        # FIXME: Mutating the dictionary and allowing it to leak to the caller
        #        is a hack!
        if ancestor_node_values:
            for ancestor_node, expected_value in ancestor_node_values.copy().items():
                if self._adaptor.applies_to(ancestor_node):
                    adapted_node = self._adaptor.adapt_node(ancestor_node)
                    adapted_value = self._adaptor.adapt_value(expected_value)
                    ancestor_node_values[adapted_node] = adapted_value

        yield from self._result.values(ancestor_node_values)

    def __repr__(self):
        return "AdpatedResult({}, {})".format(self._adaptor, self._result)

    def __str__(self):
        return repr(self)


class ResultGraph:

    def __init__(self, data_graph: DataGraph):
        self._data_graph = data_graph
        self._network = networkx.DiGraph()

    @classmethod
    def from_paths(cls, data_graph: DataGraph, paths_iter: typing.Iterable[core.Path]) -> ResultGraph:
        """
        Creates a new result graph from the given paths.
        """
        result_graph = cls(data_graph)
        for path in paths_iter:
            result_graph.construct_path_if_not_exists(path)

        return result_graph

    def construct_path_if_not_exists(self, data_path: core.Path):
        """
        Given a path through the stored data graph, constructs a result for
        each walked node in the data graph if a result doesn't already exist.
        """
        # When we are given a path, this path may not be complete. That is, there
        # may exist intermediate nodes between the nodes specified in the path.
        # "Resolve" those here. We have to be careful since the user of this API
        # is not aware of the resolved path, so when asking for a result they are
        # providing an _unresolved_ path
        resolved_path = self._data_graph.resolve_shortest_paths_within(data_path)

        prev_result = None
        prev_data_node = None
        prev_resolved_path = None
        # .foo.bar -> [.foo, .foo.bar]
        for curr_resolved_path in reversed(resolved_path.ancestor_paths(including_self=True)):
            try:
                curr_result: Result = self.result(curr_resolved_path)
                curr_data_node = curr_result.node()
            except ValueError:
                curr_data_node = self._data_graph.find_with_mangled_name(curr_resolved_path.last())
                if not prev_data_node:
                    assert not prev_result
                    curr_result = curr_data_node.result()

                elif self._data_graph.has_adaptor(prev_data_node, curr_data_node):
                    adaptor = self._data_graph.adaptor(prev_data_node, curr_data_node)
                    curr_result = AdaptedResult(curr_data_node.result(), adaptor)
                else:
                    curr_result = prev_result.join(curr_data_node)

            if prev_resolved_path:
                self._network.add_edge((prev_resolved_path, prev_result), (curr_resolved_path, curr_result))
            else:
                self._network.add_node((curr_resolved_path, curr_result))

            prev_result = curr_result
            prev_data_node = curr_data_node
            prev_resolved_path = curr_resolved_path

    def result(self, path: core.Path) -> Result:
        """
        Returns a result for the given path in the stored data graph.
        """
        resolved_path = self._data_graph.resolve_shortest_paths_within(path)

        # FIXME: We have a graph, why not use it?
        for path_and_result in self._network.nodes:
            node_path, node_result = path_and_result
            if node_path == resolved_path:
                return node_result
        raise ValueError("No such result for path: " + str(path))


ModuleMap = typing.Dict[str, types.ModuleType]


def _from_yaml_file(filepath: str, relative_dir: str) -> typing.Tuple[ModuleMap, DataGraph]:
    with open(filepath) as f:
        return _from_yaml_string(f.read(), relative_dir)


def from_yaml_file(filepath: str) -> DataGraph:
    """
    Returns a data graph constructed from the given YAML file.
    """
    relative_dir = os.path.dirname(filepath)
    _, graph = _from_yaml_file(filepath, relative_dir)
    return graph


def _from_yaml_string(yaml_string: str, relative_dir: str) \
        -> typing.Tuple[ModuleMap, DataGraph]:
    """
    Returns a data graph constructed from the given YAML string.
    """
    yaml_data = yaml.safe_load(yaml_string)
    cache = _process_cache(yaml_data)
    return _process_datasources(yaml_data, cache, relative_dir)


def from_yaml_string(yaml_string: str, relative_dir: typing.Optional[str] = None) -> DataGraph:
    """
    Returns a data graph constructed from the given YAML string.
    """
    if not relative_dir:
        relative_dir = os.getcwd()

    _, graph = _from_yaml_string(yaml_string, relative_dir)
    return graph


def _process_cache(yaml_data: dict) -> acache.AbstractCache:
    """
    Returns a acache.AbstractCache based on the cache configuration
    in the yaml data.

    cache:
      dir: filepath
    """
    cache_data = yaml_data.get("cache", {})
    if "dir" in cache_data:
        return acache.PersistentFileCache(cache_data["dir"])
    return acache.NopCache()


def _process_datasources(yaml_data: dict, cache: acache.AbstractCache, relative_dir: str) \
        -> typing.Tuple[ModuleMap, DataGraph]:
    """
    Returns a combined DataGraph from all the datasource configurations.

    external_datasources:
       - path: filepath
    datasources:
      prometheus_datasource_name:
        datasource: prometheus
        ... # prometheus-specific data
      sqlite_datasource_name:
        datasource: sqlite3
        ... # sqlite-specific data
      ...
    """
    subgraphs = []
    modules_map = {}

    if "external_datasources" in yaml_data:
        external_datasources_data = yaml_data["external_datasources"]
        for external_datasource_data in external_datasources_data:
            if "path" not in external_datasource_data:
                raise ValueError("No path given for external datasource")

            # If this config is in an e.g. etc/ dir, then the external yaml
            # files should be relative to etc/, unless an absolute path
            # is given
            external_yaml_path = external_datasource_data["path"]
            external_yaml_resolved_path = os.path.join(relative_dir, external_yaml_path)

            external_modules_map, graph = _from_yaml_file(external_yaml_resolved_path, relative_dir)
            modules_map.update(external_modules_map)
            subgraphs.append(graph)

    if "datasources" in yaml_data:
        datasources_data = yaml_data["datasources"]
        modules_map.update(_map_datasources_into_modules(datasources_data))

        for datasource_name, datasource_data in datasources_data.items():
            module = modules_map[datasource_name]  # e.g. pcp
            subgraph = module.from_yaml(datasource_name, datasource_data, cache)  # type: ignore
            subgraphs.append(subgraph)

    if not subgraphs:
        raise ValueError("No data sources ('datasources' nor 'external_datasources') "
                         "found while processing YAML")

    graph = DataGraph.combine_subgraphs(subgraphs)

    if "joins" in yaml_data:
        _process_joins(yaml_data["joins"], modules_map, graph)

    return modules_map, graph


def _map_datasources_into_modules(datasources_data: typing.Dict[str, dict]) -> ModuleMap:
    # datasources:
    #   datasource_name:
    #     datasource: prometheus
    #     ...
    datasource_name_to_module_map = {}
    for datasource_name, datasource_data in datasources_data.items():
        datasource_type = datasource_data["datasource"]
        if datasource_type == "prometheus":
            from . import prometheus
            datasource_name_to_module_map[datasource_name] = prometheus
        elif datasource_type == "sqlite3" or datasource_type == "sqlite":
            from . import sqlite
            datasource_name_to_module_map[datasource_name] = sqlite
        elif datasource_type == "test":
            from . import test
            datasource_name_to_module_map[datasource_name] = test
        elif datasource_type == "pcp":
            from . import pcp
            datasource_name_to_module_map[datasource_name] = pcp
        elif datasource_type == "influxdb" or datasource_type == "influx":
            from . import influx
            datasource_name_to_module_map[datasource_name] = influx
        else:
            raise ValueError("Unknown datasource plugin with name " + datasource_type)

    return datasource_name_to_module_map


def _process_joins(joins_data: typing.List[dict], module_map: ModuleMap, graph: DataGraph):
    # joins:
    #   - to_datasource_name.to_datasource_identifier: from_datasource_name.from_datasource_identifier
    #     relabel_map:
    #       from_value: to_value
    #
    # e.g. (where infradb is a SQLite3 datasource, prom is a Prometheus datasource)
    #   - infradb.location.rack: prom.rack
    #   - infradb.location.hostname: prom.instance
    #     relabel_map:
    #       compute1: compute1.hpc.institution.edu
    #       compute2: compute2.hpc.institution.edu
    for join_data in joins_data:
        ignored_keys = {"relabel_map"}
        # e.g. Find node in data graph of e.g. tsdata.label or db.table.column
        from_datasource_identifier = list(set(join_data.keys()) - ignored_keys)[0]
        to_datasource_identifier = join_data[from_datasource_identifier]

        # e.g. infradb.location.row: prometheus.row
        from_datasource_name, from_identifier = from_datasource_identifier.split(".", maxsplit=1)
        from_module = module_map[from_datasource_name]
        from_name = from_module.node_name_from_yaml_identifier(from_identifier)  # type: ignore

        to_datasource_name, to_identifier = to_datasource_identifier.split(".", maxsplit=1)
        to_module = module_map[to_datasource_name]
        to_name = to_module.node_name_from_yaml_identifier(to_identifier)  # type: ignore

        from_node = graph.find(from_datasource_name, from_name)
        to_node = graph.find(to_datasource_name, to_name)

        if "relabel_map" not in join_data:
            adaptor = DirectionalNodeAdaptor(from_node, to_node)
        else:
            adaptor = RelabelNodeAdaptor(from_node, to_node, join_data["relabel_map"])

        graph.add_edge_node(from_node, to_node)
        # FIXME: Don't reach into private
        graph._adaptors[(from_node, to_node)] = adaptor


def dump_yaml(datasource_name: str, datasource_data: dict):
    return yaml.safe_dump({"datasources": {datasource_name: datasource_data}}, sort_keys=False)
