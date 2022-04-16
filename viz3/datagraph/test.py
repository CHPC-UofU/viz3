# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Defines a test data source.

Used for testing, and as an example of a simple data source.
"""

import typing

import networkx
import pandas
import more_itertools

from .. import datagraph


class TestDataGraph(datagraph.DataGraph):

    def __init__(self, datasource_name: str, dataframe: pandas.DataFrame):
        super().__init__()
        self._datasource_name = datasource_name
        self._dataframe = dataframe

    def _create_node(self, column_name: str):
        return TestNode(
            self._dataframe,
            self._datasource_name,
            column_name,
        )

    def construct_node(self, to_column_name: str, from_column_name: typing.Optional[str] = None):
        node = self._create_node(to_column_name)
        if not from_column_name:
            self.add_node(node)
        else:
            try:
                from_node = self.find_by_column(from_column_name)
            except ValueError:
                from_node = self._create_node(from_column_name)

            self.add_edge_node(from_node, node)

        return node

    def find_by_column(self, column_name: str):
        return self.find(self._datasource_name, column_name)


class TestNode(datagraph.DataNode):

    def __init__(self, dataframe: pandas.DataFrame, datasource_name: str, column_name: str):
        super().__init__(datasource_name, column_name, str)
        self._dataframe = dataframe

    def column_name(self):
        return self.name()

    def dataframe(self):
        return self._dataframe

    def result(self):
        return TestResult(self, self._dataframe)


class TestResult(datagraph.Result):

    def __init__(self, node: datagraph.DataNode, dataframe: pandas.DataFrame):
        super().__init__(node)
        self._dataframe = dataframe

    def join(self, other_node: datagraph.DataNode) -> datagraph.Result:
        node = self.node()
        assert isinstance(node, TestNode)

        if isinstance(other_node, TestNode):
            our_dataframe = node.dataframe()
            other_dataframe = other_node.dataframe()

            joined_dataframe = pandas.concat([our_dataframe, other_dataframe], join="inner", keys=[other_node.column_name()])
            #joined_dataframe = our_dataframe.join(other_dataframe, on=node.column_name())
            return TestResult(other_node, joined_dataframe)

        assert False

    def comparable_node_values(self, ancestor_node_values: datagraph.NodeValues) \
            -> typing.Dict[TestNode, typing.Any]:
        node = self.node()
        assert isinstance(node, TestNode)

        node_values: typing.Dict[TestNode, typing.Any] = {}
        for ancestor_node, expected_value in ancestor_node_values.items():
            if (isinstance(ancestor_node, TestNode)
                    and ancestor_node.datasource_name() == node.datasource_name()):
                node_values[ancestor_node] = expected_value

        return node_values

    def values(self, ancestor_node_values: typing.Optional[datagraph.NodeValues] = None) \
            -> typing.Iterable[typing.Any]:
        if not ancestor_node_values:
            ancestor_node_values = {}

        node = self.node()
        assert isinstance(node, TestNode)

        # FIXME: This selection is probably not efficent.
        df = self._dataframe.copy()
        for ancestor_node, value in self.comparable_node_values(ancestor_node_values).items():
            df = df[df[ancestor_node.column_name()] == value]

        yield from more_itertools.unique_everseen(df.loc[:, node.column_name()].values)


def create_data_graph_from_dataframe(dataframe: pandas.DataFrame,
                                     datasource_name: str,
                                     graph: networkx.DiGraph):
    test_graph = TestDataGraph(datasource_name, dataframe)

    for from_name, to_name in graph.edges:
        test_graph.construct_node(to_name, from_name)

    return test_graph


def node_name_from_yaml_identifier(yaml_identifier: str) -> str:
    # YAML identifiers refer directly to node names
    return yaml_identifier


def from_yaml(datasource_name, datasource_data, cache):
    # test_host:
    #   datasource: test
    #   graph:
    #     - cluster: [hostname]
    #   table:
    #     - hostname: "1.cluster1"
    #       cluster: "cluster1"
    #     - hostname: "2.cluster1"
    #       cluster: "cluster1"
    #     - hostname: "1.cluster2"
    #       cluster: "cluster2"
    assert datasource_data["datasource"] == "test"

    graph = networkx.DiGraph()
    dataframe = pandas.DataFrame.from_records(datasource_data["table"])
    for adj in datasource_data["graph"]:
        for from_column_name, to_column_names in adj.items():  # from_node = cluster, to_node = [hostname]
            if len(to_column_names) < 1:
                raise ValueError("Empty list found for {} adjacency in graph "
                                 "specification".format(from_column_name))

            for to_column_name in to_column_names:
                graph.add_edge(from_column_name, to_column_name)

    return create_data_graph_from_dataframe(dataframe, datasource_name, graph)
