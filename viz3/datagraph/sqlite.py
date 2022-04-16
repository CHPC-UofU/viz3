# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Defines a Sqlite3 data source according to datagraph.py.
"""
import collections
import dataclasses
import functools
import logging
import sqlite3
import typing

from .. import acache
from .. import datagraph

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def mangle_table_and_column_names(table_name: str, column_name: str) -> str:
    return "{}_{}".format(table_name, column_name)


@dataclasses.dataclass(frozen=True)
class Key:
    name: str
    # These may refer to a non-foreign table/name if key is not foreign
    foreign_table_name: str
    foreign_name: str

    def foreign_identifier(self):
        return self.foreign_table_name + "." + self.foreign_name


@dataclasses.dataclass
class Sqlite3Table:
    table_name: str
    primary_keys: typing.List[Key]
    value_keys: typing.List[Key]
    category_keys: typing.Dict[Key, typing.List[str]]

    def foreign_keys(self) -> typing.List[Key]:
        return [
            key
            for key in self.primary_keys
            if key.foreign_table_name != self.table_name
        ]

    def __contains__(self, key: Key):
        assert isinstance(key, Key)
        return any(self_key == key for self_key in self.primary_keys + self.value_keys)


class Sqlite3Querier:

    def __init__(self, filepath: str):
        self._filepath = filepath

    def query(self, statement: str):
        conn = sqlite3.connect(self._filepath)
        cursor = conn.cursor()
        cursor.execute(statement)
        results = cursor.fetchall()
        cursor.close()
        conn.commit()
        return results


class Sqlite3DataGraph(datagraph.DataGraph):

    def __init__(self, querier: Sqlite3Querier, datasource_name: str):
        self._querier = querier
        self._datasource_name = datasource_name
        super().__init__()

    def _create_sqlite3_column(self, key: Key, table: Sqlite3Table):
        return Sqlite3Column(
            self._querier,
            self._datasource_name,
            key.name,
            table,
        )

    def construct_sqlite3_column(self, key: Key, table: Sqlite3Table, from_col: typing.Optional['Sqlite3Column'] = None):
        if key.foreign_table_name != table.table_name:
            # We are referencing a foreign key; look it up and return it!
            return self.find_by_column(key.foreign_table_name, key.foreign_name)

        column_node = self._create_sqlite3_column(key, table)
        if not from_col:
            self.add_node(column_node)
        else:
            try:
                self.add_node(column_node, from_col)
            except ValueError:
                assert False

        return column_node

    def find_by_column(self, table_name: str, column_name: str):
        return self.find(self._datasource_name, mangle_table_and_column_names(table_name, column_name))


class Sqlite3Column(datagraph.DataNode):

    def __init__(self, querier: Sqlite3Querier, datasource_name: str, column_name: str, table: Sqlite3Table):
        name = mangle_table_and_column_names(table.table_name, column_name)
        super().__init__(datasource_name, name, str)
        self._querier = querier
        self._table = table
        self._column_name = column_name

    def table(self):
        return self._table

    def table_name(self):
        return self.table().table_name

    def column_name(self):
        return self._column_name

    def identifier(self):
        return self.table_name() + "." + self.column_name()

    def querier(self):
        return self._querier

    def result(self):
        return Sqlite3Result(self)


class Sqlite3Result(datagraph.Result):

    def __init__(self, column: Sqlite3Column, prev_result: typing.Optional['Sqlite3Result'] = None):
        super().__init__(column)
        self._prev_result = prev_result
        self._cache = acache.InMemoryCache()

    def _foreign_keys_in_chain(self, references_keys: typing.Optional[typing.List[Key]] = None) \
            -> typing.Iterable[Key]:
        node = self.node()
        assert isinstance(node, Sqlite3Column)

        if not references_keys:
            references_keys = node.table().foreign_keys()

        assert references_keys is not None
        for reference_key in references_keys:
            if reference_key.foreign_identifier() == node.identifier():
                references_keys.remove(reference_key)
                yield reference_key

        if self._prev_result:
            yield from self._prev_result._foreign_keys_in_chain(references_keys)

    @functools.lru_cache
    def _foreign_table_accesses_in_chain(self) -> typing.Dict[str, typing.List[Key]]:
        foreign_keys_by_table = collections.defaultdict(list)
        for foreign_key in self._foreign_keys_in_chain():
            foreign_keys_by_table[foreign_key.foreign_table_name].append(foreign_key)

        return foreign_keys_by_table

    def join(self, other_node: datagraph.DataNode) -> datagraph.Result:
        node = self.node()
        assert isinstance(node, Sqlite3Column)
        if isinstance(other_node, Sqlite3Column) and other_node.datasource_name() == node.datasource_name():
            return Sqlite3Result(other_node, self)
        return other_node.result()

    def column_constraints_from_node_values(self, ancestor_node_values: datagraph.NodeValues) \
            -> typing.Dict[str, typing.Any]:
        node = self.node()
        assert isinstance(node, Sqlite3Column)

        foreign_table_names = set(self._foreign_table_accesses_in_chain())

        column_constraints = {}
        for ancestor_node, expected_value in ancestor_node_values.items():
            if (not isinstance(ancestor_node, Sqlite3Column)
                    or ancestor_node.datasource_name() != node.datasource_name()):
                continue

            ancestor_table_name = ancestor_node.table_name()
            if ancestor_table_name == node.table_name() or ancestor_table_name in foreign_table_names:
                column_constraints[ancestor_node.identifier()] = expected_value

        return column_constraints

    def _query_values(self, *column_names: str) -> typing.List[typing.Dict[str, typing.Any]]:
        node = self.node()
        assert isinstance(node, Sqlite3Column)
        table_name = node.table_name()

        join = ""
        for foreign_table_name, foreign_keys in self._foreign_table_accesses_in_chain().items():
            join_on_clauses = []
            for foreign_key in foreign_keys:
                join_on_clauses.append("{}.{} = {}.{}".format(
                    table_name,
                    foreign_key.name,
                    foreign_key.foreign_table_name,
                    foreign_key.foreign_name
                ))

            join += " JOIN {} ON {}".format(foreign_table_name, " AND ".join(join_on_clauses))

        selector = ", ".join(column_names)
        statement = "SELECT DISTINCT {} FROM {}{} ORDER BY {}".format(selector, table_name, join, selector)
        logger.debug("executing %s", statement)

        values = []
        for row_values in node.querier().query(statement):
            values.append({c: v for c, v in zip(column_names, row_values)})

        return values

    def values(self, ancestor_node_values: typing.Optional[datagraph.NodeValues] = None) \
            -> typing.Dict[str, typing.Any]:
        if not ancestor_node_values:
            ancestor_node_values = {}

        column_constraints = self.column_constraints_from_node_values(ancestor_node_values)

        node = self.node()
        assert isinstance(node, Sqlite3Column)
        column_id = node.identifier()
        other_column_ids = list(column_constraints.keys())
        other_column_ids.append(column_id)
        cache_id = "_".join(list(sorted(other_column_ids)))

        for values in self._cache.retrieve_or_update(column_id, cache_id, self._query_values, *other_column_ids):
            skipped_a_row = False
            for key, value in values.items():
                if key in column_constraints and column_constraints.get(key) != value:
                    skipped_a_row = True
                    break

            if not skipped_a_row:
                yield values[column_id]


def create_graph_from_schema(querier: Sqlite3Querier,
                             datasource_name: str,
                             tables: typing.List[Sqlite3Table]):
    graph = Sqlite3DataGraph(querier, datasource_name)

    # We associated the values of a table with the last primary key in the
    # primary key "chain" (order found in the table), so keep those around
    last_col_per_table = {}
    for table in tables:
        table_name = table.table_name

        prev_col = None
        for primary_key in table.primary_keys:
            prev_col = graph.construct_sqlite3_column(
                key=primary_key,
                table=table,
                from_col=prev_col,
            )

        last_col_per_table[table_name] = prev_col

    # Iterate again, after all primary keys of tables has been constructed,
    # so that foreign columns are guaranteed to exist
    for table in tables:
        table_name = table.table_name

        for value_key in table.value_keys:
            # It does not make sense to claim a value in another foreign table,
            # particularly because that may lead to duplicate values
            assert value_key.foreign_table_name == table_name
            graph.construct_sqlite3_column(
                key=value_key,
                table=table,
                from_col=last_col_per_table[table_name]
            )

    # Iterate once more, after all value keys and primary keys have been
    # constructed so that all keys that we are categorizing are
    # guaranteed to exist
    for table in tables:
        table_name = table.table_name

        for category_key, subset_key_names in table.category_keys.items():
            category_col = graph.construct_sqlite3_column(
                key=category_key,
                table=table,
            )

            for subset_key_name in subset_key_names:
                graph.add_intermediate_node(category_col, graph.find_by_column(table_name, subset_key_name))

    return graph


def node_name_from_yaml_identifier(yaml_identifier: str) -> str:
    # Table and columns in YAML are identified by table.column
    table_name, column_name = yaml_identifier.split(".", maxsplit=1)
    return mangle_table_and_column_names(table_name, column_name)


def from_yaml(datasource_name, datasource_data, cache):
    #   infradb:
    #     datasource: sqlite3
    #     filepath: "data/infra.db"
    #     tables:
    #       location:
    #         primary_keys: [datacenter, row, rack, slot]
    #         category_keys:
    #           room: [pod]
    #           pod: [row]
    #       pdu:
    #         primary_keys: [datacenter, row, rack, slot]
    #         foreign_keys:
    #           datacenter: "location.datacenter"
    #           row: "location.row"
    #           rack: "location.rack"
    #           slot: "location.slot"
    #         values: [hostname]
    assert datasource_data["datasource"] == "sqlite3"

    filepath = datasource_data["filepath"]
    querier = Sqlite3Querier(filepath)

    tables = []
    for table_name, table_data in datasource_data["tables"].items():
        primary_keys = []
        for primary_key_name in table_data["primary_keys"]:
            primary_keys.append(Key(name=primary_key_name, foreign_table_name=table_name, foreign_name=primary_key_name))

        for local_key_name, foreign_table_name_dot_key in table_data.get("foreign_keys", {}).items():
            for i, primary_key in enumerate(primary_keys):
                if primary_key.name == local_key_name:
                    foreign_table_name, foreign_name = foreign_table_name_dot_key.split(".", maxsplit=1)
                    primary_keys[i] = Key(name=local_key_name, foreign_table_name=foreign_table_name, foreign_name=foreign_name)
                    break
            else:
                assert False

        value_keys = []
        for value_key_name in table_data.get("values", []):
            value_keys.append(Key(value_key_name, table_name, value_key_name))

        category_keys = collections.defaultdict(list)
        for category_key_name, subset_key_names in table_data.get("category_keys", {}).items():
            assert all(key.name != category_key_name for key in primary_keys + value_keys)
            category_key = Key(name=category_key_name, foreign_table_name=table_name, foreign_name=category_key_name)
            for subset_key_name in subset_key_names:
                for key in list(category_keys.keys()) + value_keys + primary_keys:
                    if key.name == subset_key_name:
                        category_keys[category_key].append(key.name)
                        break
                else:
                    assert False

        table = Sqlite3Table(
            table_name,
            primary_keys,
            value_keys,
            category_keys,
        )
        tables.append(table)

    return create_graph_from_schema(querier, datasource_name, tables)
