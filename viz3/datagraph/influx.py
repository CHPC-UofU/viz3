# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Defines a InfluxDB v1 data source according to datagraph.py.

This is arguably the most organized module of the database modules, but
it is still messy, since InfluxDB is not nice to programmatically query thanks
to it's treatment of tags and fields (columns) within a measurement (tables)
differently, unlike in a relational database.

From an efficiency standpoint, this module is also not going to be as aggressive
in combining data nodes into singular queries when compared to SQLite (also a
table-like data source) since InfluxDB v1 doesn't have JOINs.
"""
import abc
import collections
import datetime
import logging
import typing

from .. import datagraph
from .. import acache

import influxdb
import influxdb.resultset
import yaml

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def mangle_measurement_column_name(measurement_name: str, name: str):
    """
    Combines a measurement and column (tag or field) string. Non-reversible.
    """
    # not using dot because Path() separates using that
    return measurement_name + "_" + name


def datetime_to_rfc3339(dt: datetime.datetime) -> str:
    """
    Converts a datetime object to RFC3339, a format similar to ISO8601
    (e.g. 2022-02-25 00:35:31) that InfluxDB uses.
    """
    # InfluxDB expects RFC 3339, which is UTC. The format itself it essentially
    # ISO 8601, except "T" is sandwhiched in the middle instead of a space, and
    # a 'Z' at the end to denote zulu (zero) offset from UTC
    return dt.utcnow().isoformat("T") + "Z"


def rfc3339_to_datetime(rf3339: str) -> datetime.datetime:
    """
    Converts a RFC3339 string (e.g. 2022-02-25T00:35:31Z) to a datetime object.
    """
    # See datetime_to_rfc3339
    return datetime.datetime.fromisoformat(rf3339.rstrip("Z"))


string_type_map = {
    "int": int,
    "str": str,
    "string": str,
    "float": float,
    "bool": bool,
    "time": datetime.datetime,
    "bytes": bytes,
}


# Valid InfluxDB types encoded in Python
InfluxDBTypes = typing.Union[int,str,float,bool,datetime.datetime,bytes]
# Rows returned by the Querier, the dictionary maps columns (tags/fields) to values
Rows = typing.List[typing.Dict[str, InfluxDBTypes]]
# A grouping of influxdb values or just influxdb values
InfluxDBTypeOrList = typing.Union[InfluxDBTypes, typing.List[InfluxDBTypes]]
# Grouped rows
CombinedRows = typing.List[typing.Dict[str, InfluxDBTypeOrList]]


class InfluxDBQuerier:
    """
    Executes queries on an InfluxDB database.
    """

    def __init__(self, host: str, database: str, username: str, password: str,
                 proxy: typing.Optional[str] = None,
                 cache: typing.Optional[acache.AbstractCache] = None):
        proxy_dict = {"http": proxy} if proxy else {}
        self._host = host
        self._port = 8086
        if ":" in self._host:
            self._host, self._port = self._host.split(":", maxsplit=1)
        self._database = database
        self._username = username
        self._password = password
        self._proxy = proxy
        self._client = influxdb.InfluxDBClient(
            host=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            database=self._database,
            proxies=proxy_dict
        )
        self._cache: acache.AbstractCache = acache.NopCache()
        if cache is not None:
            self._cache = cache

    def cache(self) -> acache.AbstractCache:
        return self._cache

    def target(self) -> str:
        host = self._host
        if ":" in host:
            return host
        return self._host + ":8086"

    def database(self) -> str:
        return self._database

    def username(self) -> str:
        return self._username

    def password(self) -> str:
        return self._password

    def proxy(self) -> typing.Optional[str]:
        return self._proxy

    @acache.class_fallback_cache
    def measurement_names(self) -> typing.List[str]:
        """
        Returns a list of measurement names within the configured database.
        """
        # https://influxdb-python.readthedocs.io/en/latest/api-documentation.html#influxdb.InfluxDBClient.get_list_measurements
        return [d["name"] for d in self._client.get_list_measurements()]

    @acache.class_fallback_cache
    def field_types(self, measurement_name: str) -> typing.Dict[str, typing.Type]:
        """
        Returns a dictionary mapping fields within the given measurement to their
        Python type.
        """
        logger.debug("Querying fields for measurement %s", measurement_name)
        fields_result = self._client.query("SHOW FIELD KEYS FROM " + measurement_name)

        # [{'fieldKey': 'busid', 'fieldType': 'string'}, ...]
        field_types = {}
        for result_dict in fields_result.get_points():
            field_types[result_dict["fieldKey"]] = yaml_type_string_to_type(result_dict["fieldType"])

        return field_types

    @acache.class_fallback_cache
    def tags(self, measurement_name: str) -> typing.Set[str]:
        """
        Returns the set of tags belonging to the given measurement.
        """
        logger.debug("Querying tags for measurement %s", measurement_name)
        tags_result = self._client.query("SHOW TAG KEYS FROM " + measurement_name)

        # [{'tagKey': 'cluster'}, {'tagKey': 'host'}, {'tagKey': 'instance'}]
        tags = set()
        for result_dict in tags_result.get_points():
            tags.add(result_dict["tagKey"])

        return tags

    @acache.class_fallback_cache
    def run_query(self, query_string: str) -> Rows:
        """
        Runs a query against InfluxDB, returning the list of rows returned from
        the query. Each row is a dictionary mapping the selected fields to their
        value. Additionally, each row contains a "time" field, which is a datetime
        object.
        """
        logger.debug("Querying %s", query_string)
        result = self._client.query(query_string)
        assert isinstance(result, influxdb.resultset.ResultSet)
        raw_result = result.raw["series"]

        # {'series': [{'columns': ['time',
        #                          'temp',
        #                          'cardname'],
        #              'name': 'nvidia',
        #              'tags': {'cluster': '"notchpeak"',
        #                       'host': '"notch001"',
        #                       'instance': 'gpu0'},
        #              'values': [['1970-01-01T00:00:00Z',
        #                          30.0,
        #                          'Tesla A100']]}, ...]
        results = []
        for raw_result_dict in raw_result:
            result_dict = dict(zip(raw_result_dict["columns"], raw_result_dict["values"][0]))
            result_dict.update(raw_result_dict.get("tags", {}))
            # FIXME? If a time range is not specified, then the time column
            #        will be zero  aka 1970 epoch if last() or aggregation
            #        functions are used in the query.
            result_dict["time"] = rfc3339_to_datetime(result_dict["time"])
            results.append(result_dict)

        return results

    @staticmethod
    def _parse_series_csv(string):
        """
        Parses a string of the form, where any 'value' can be quoted:
        'measurement,tag=value,tag=...'
        or 'measurement,tag="value",tag=...'

        i.e. the beginning of a InfluxDB line format, without the fields or timestamp.
        """
        measurement_name, rest = string.split(",", maxsplit=1)

        tag_values = {}
        while rest != "":
            i = rest.find("=")
            tag = rest[:i]
            if rest[i + 1] == '"':
                j = rest[i + 2:].find('"') + i + 2
                tag_value = rest[i + 2: j]
                j += 2  # add ,
            else:
                j = rest.find(",")
                if j == -1:
                    j = len(rest)
                tag_value = rest[i + 1:j]
                j += 1

            tag_values[tag] = tag_value
            rest = rest[j:]

        return measurement_name, tag_values

    @acache.class_fallback_cache
    def series(self, tags: typing.Set[str], measurement_name: typing.Optional[str] = None) \
            -> Rows:
        """
        Returns a list of dictionaries containing distinct tag tuple values.

        >>> self.series({"host", "cpu"})
        [{"host": "host1", "cpu": "1"}
         {"host": "host1", "cpu": "2"}
         {"host": "host1", "cpu": "3"}
         {"host": "host1", "cpu": "4"}
         {"host": "host2", "cpu": "1"}
         {"host": "host2", "cpu": "2"}
         ...]
        """
        logger.debug("Querying series for tags %s", tags)
        # AFAIK there is no way to query this information in InfluxDB since SELECTs
        # require querying fields, which we do know at this point and SHOW TAG VALUES
        # only returns values for a singular tag. SHOW SERIES will show _all_ the
        # distinct tag values for each measurement, which we'll have to process here
        # to select the subset of those tags and make them distinct again...
        #
        # != null is our trick to only select measurements where that tag exists
        where_clause = " AND ".join(tag + " != null" for tag in tags)

        from_clause = ""
        if measurement_name:
            from_clause = " FROM " + measurement_name

        result = self._client.query("SHOW SERIES" + from_clause + " WHERE " + where_clause)
        assert isinstance(result, influxdb.resultset.ResultSet)
        # [{'key': 'nvidia,cluster=notchpeak,host=notch309,instance=gpu0'}, ...]
        # We get more tags than we asked for; so need to do the deduplicaiton/merging
        # ourselves

        series = []
        for result_dict in result.get_points():
            measurement_name, tag_values = self._parse_series_csv(result_dict["key"])
            series.append(tag_values)

        tags_ordered = list(sorted(tags))  # sets are not ordered; needed for rewrapping logic
        distinct_tuples = set()
        for tag_values in series:
            distinct_tuples.add(tuple(tag_values[tag] for tag in tags_ordered))

        return [
            {tags_ordered[i]: tag_value for i, tag_value in enumerate(tup)}
            for tup in distinct_tuples
        ]


class InfluxDBMeasurement:
    """
    A software representation of a measurement in InfluxDB. The set of fields
    and tags here are subsets of the fields and tags in the database measurement.
    """

    def __init__(self, measurement_name: str, tags: typing.Set[str],
                 field_types: typing.Dict[str, typing.Type]):
        self._measurement_name = measurement_name
        self._tags = tags
        self._field_types = field_types

    def measurement_name(self):
        return self._measurement_name

    def tags(self) -> typing.Set[str]:
        return self._tags

    def fields(self) -> typing.Set[str]:
        return set(self._field_types)

    def field_types(self) -> typing.Dict[str, typing.Type]:
        return self._field_types.copy()

    def columns(self) -> typing.Set[str]:
        return self.tags() | self.fields()

    @staticmethod
    def combine(*measurements: 'InfluxDBMeasurement'):
        """
        Returns a new measurement with combined tags and fields. Assumes the
        measurement names are the same.
        """
        assert len(measurements) > 1
        assert len(set(s.measurement_name() for s in measurements)) == 1
        measurement_name = measurements[0].measurement_name()
        tags = set()
        field_types = {}
        for measurement in measurements:
            tags.update(measurement.tags())
            field_types.update(measurement.field_types())

        return InfluxDBMeasurement(
            measurement_name=measurement_name,
            tags=tags,
            field_types=field_types,
        )

    def as_query(self, start: typing.Optional[datetime.datetime] = None,
                 end: typing.Optional[datetime.datetime] = None) -> str:
        """
        Returns a query that selects the fields and tags of this measurement
        where all the tags corresponding to the measurement in the database are
        distinct. e.g. ('host', 'cpu') tags with a 'usage' field would return
        usage values for every CPU on every host within the database, assuming
        host and cpu were the only tags.

        NOTE: This does not return _distinct_ values for the tags stored in this
              class, unless the set of tags is the same as the tags in the
              database measurement. This is because InfluxDB fundamentally doesn't
              support distinctness on a subset of tags, even with hacks.

        NOTE: Queries selecting tags without fields should not use this method!
              (it requires a more complicated software driven process that
               cannot be done without additional software processing; see
               InfluxDBQuerier.series)

        If a start or end datetime range is not given, the last values in the
        database are returned.
        """
        assert len(self.fields()) >= 1  # use series() otherwise (SELECT only works on fields)

        where_statement = " WHERE "
        if start:
            where_statement += "time >= '{}'".format(datetime_to_rfc3339(start))
            if end:
                where_statement += " AND "
        if end:
            where_statement += "time < '{}'".format(datetime_to_rfc3339(end))
        if not start and not end:
            where_statement = ""

        # Sort for consistent queries when fields/sets are the same
        ordered_fields = list(sorted(self.fields()))

        # Note: The time returned by InfluxDB in a SELECT query is always zero
        #       if any aggregation (such as last()) occurs.
        #       https://github.com/influxdata/influxdb/issues/3337
        if start or end:
            fields_joined = ", ".join(ordered_fields)
        else:
            # If we don't do this AS alias, the column name will be last_N, where N
            # is the selector index; we want to easily map column names to their
            # values without having to carry a list of columns to index the
            # results by
            fields_joined = ", ".join("last({}) AS {}".format(f, f) for f in ordered_fields)

        # GROUP BY, when combined with last(), returns the last() group of the
        # series, NOT the last _series_ grouped. So, we always need to do
        # GROUP BY *, so that we pull everything.
        #
        # This grouping however, does not achieve the selection of
        # distinct values with regard to a tag subset of the measurement
        # tag set. This requires software processing. (distinct() in Influx
        # only works for a singular field, GROUP BY doesn't enforce uniqueness,
        # one cannot mix aggregation and non-aggregation statements either
        # (thus, one cannot do the equivalent of assigning each unique
        # tuple a number and then doing a WHERE numbers equal), also string
        # concatenation doesn't exist preventing the same WHERE uniqueness
        # trick, but with strings. InfluxDB, I hate to break it to you,
        # but your strict separation of tags and fields sucks and combines
        # the worst of both relational and NoSQL databases...)
        return "SELECT {} FROM {}{} GROUP BY *".format(
            fields_joined,
            self.measurement_name(),
            where_statement,
        )


class InfluxDBConstraint:
    """
    A set of tags and fields values that a returned query row should be
    constrained against.

    The assumption here is that the tags and fields are all from the same
    measurement, as JOINs in InfluxDB are non-existent and we don't have any
    data structures encoding such notion.
    """

    def __init__(self, fields: typing.Dict[str, InfluxDBTypes], tags: typing.Dict[str, str]):
        self._fields = fields
        self._tags = tags

    def tags(self) -> typing.Set[str]:
        return set(self._tags)

    def fields(self) -> typing.Set[str]:
        return set(self._fields)

    def field_types(self) -> typing.Dict[str, typing.Type]:
        return {field: type(val) for field, val in self._fields.items()}

    def column_matches(self, key: str, value: InfluxDBTypeOrList) -> bool:
        """
        Returns whether the given key and value matches against the constraints.
        i.e. if all keys within a row return True for this function, then the row
             can be kept.
        """
        if len(self._fields) == 0 and len(self._tags) == 0:
            return True

        if key not in self._fields and key not in self._tags:
            return True

        for tag, tag_value in self._tags.items():
            if tag != key:
                continue
            if isinstance(value, list):
                if tag_value in value:
                    return True
            elif tag_value == value:
                return True

        for field, field_value in self._fields.items():
            if field != key:
                continue
            if isinstance(value, list):
                if field_value in value:
                    return True
            elif field_value == value:
                return True
        return False

    def __repr__(self):
        return "InfluxDBConstraint(tags={}, fields={})".format(
            self._tags,
            self._fields,
        )

    def __str__(self):
        return self.__repr__()


class InfluxDBDataGraph(datagraph.DataGraph):

    def __init__(self, querier: InfluxDBQuerier, datasource_name: str):
        super().__init__()
        self._querier = querier
        self._datasource_name = datasource_name
        self._tag_nodes = collections.defaultdict(list)

    @classmethod
    def graph_from_measurements(cls, querier: InfluxDBQuerier, datasource_name: str,
                                *measurements: InfluxDBMeasurement) -> 'InfluxDBDataGraph':
        """
        Constructs a InfluxDBDataGraph from the given measurements.
        """
        graph = InfluxDBDataGraph(querier, datasource_name)

        for measurement in measurements:
            ancestor_tags = set()
            for tag in measurement.tags():
                tag_node = graph.construct_influxdb_tag(measurement.measurement_name(), tag)
                ancestor_tags.add(tag_node)

            for field, field_type in measurement.field_types().items():
                graph.construct_influxdb_field(
                    measurement.measurement_name(),
                    field,
                    field_type,
                    *ancestor_tags
                )

        return graph

    def find_shared_tag(self, tag: str):
        return self.find(self._datasource_name, tag)

    def find_by_column(self, measurement_name: str, column_name: str):
        return self.find(self._datasource_name, mangle_measurement_column_name(measurement_name, column_name))

    def _create_influxdb_measurement_tag(self, measurement_name: str, tag: str):
        return InfluxDBMeasurementTagNode(
            querier=self._querier,
            datasource_name=self._datasource_name,
            measurement_name=measurement_name,
            tag=tag
        )

    def _create_influxdb_shared_tag(self, tag: str):
        return InfluxDBSharedTagNode(
            querier=self._querier,
            datasource_name=self._datasource_name,
            tag=tag
        )

    def _create_influxdb_measurement_field(self, measurement_name: str, field: str,
                                           field_type: typing.Type):
        return InfluxDBMeasurementFieldNode(
            querier=self._querier,
            datasource_name=self._datasource_name,
            measurement_name=measurement_name,
            field=field,
            typeof=field_type
        )

    def construct_influxdb_tag(self, measurement_name: str, tag: str) -> 'InfluxDBNode':
        tag_node = self._create_influxdb_measurement_tag(measurement_name, tag)
        self.add_node(tag_node)

        # Always add a parent tag without the measurement prefix so that
        # multiple  fields across different measurements can be selected using
        # the same node (e.g. .host.cpu_usage, .host.mem_usage instead of
        # .mem_host.mem_usage and .cpu_host.cpu_usage); this is important
        # for the relative queries used when mapping queries to viz3 layouts
        try:
            shared_tag_node = self.find_shared_tag(tag)
        except ValueError:
            shared_tag_node = self._create_influxdb_shared_tag(tag)

        self.add_edge_node(shared_tag_node, tag_node)
        return tag_node

    def construct_influxdb_field(self, measurement_name: str, field: str,
                                 field_type: typing.Type,
                                 *from_tag_nodes: typing.Optional['InfluxDBNode']) \
            -> 'InfluxDBNode':
        field_node = self._create_influxdb_measurement_field(measurement_name, field, field_type)
        self.add_node(field_node)
        for from_tag_node in from_tag_nodes:
            self.add_node(field_node, from_tag_node)

        return field_node


class InfluxDBNode(datagraph.DataNode, abc.ABC):
    """
    An abstract class for storing InfluxDB data within a node, along with a
    query object that is used for retrieving values.
    """

    def __init__(self, querier: InfluxDBQuerier, datasource_name: str,
                 name: str, type: typing.Type = str):
        super().__init__(datasource_name, name, type)
        self._querier = querier

    def querier(self) -> 'InfluxDBQuerier':
        """
        Returns an object that can query InfluxDB.
        """
        return self._querier

    @abc.abstractmethod
    def result(self) -> 'InfluxDBResult':
        raise NotImplementedError()


class InfluxDBSharedTagNode(InfluxDBNode):
    """
    Stores an InfluxDB tag shared between all measurements, within a node
    (i.e. this node should have outgoing edges to all measurement tags
          (InfluxDBMeasurementTagNode)).

    Used for selecting tag values across multiple measurements.
    """

    def __init__(self, querier: InfluxDBQuerier, datasource_name: str, tag: str):
        super().__init__(querier, datasource_name, tag, str)

    def tag(self) -> str:
        return self.name()

    def result(self) -> 'InfluxDBSharedTagResult':
        return InfluxDBSharedTagResult(self, {self.tag()})


class InfluxDBMeasurementNode(InfluxDBNode, abc.ABC):
    """
    Abstract class storing an InfluxDB measurement column (either tag or field).
    """

    def __init__(self, querier: InfluxDBQuerier, datasource_name: str,
                 measurement_name: str, column_name: str, typeof: typing.Type):
        name = mangle_measurement_column_name(measurement_name, column_name)
        self._column_name = column_name
        super().__init__(querier, datasource_name, name, typeof)
        self._measurement_name = measurement_name

    def column_name(self) -> str:
        """
        Either a tag or field.
        """
        return self._column_name

    def measurement_name(self) -> str:
        return self._measurement_name

    @abc.abstractmethod
    def partial_measurement(self) -> InfluxDBMeasurement:
        """
        Returns an InfluxDBMeasurement object containing the tag or field
        stored within this node.

        The word 'partial' is used to signify that the measurement does not
        neccessarily contain all possible tags and fields corresponding to the
        database measurement, by virtue of only containing a singular tag
        or field.
        """
        raise NotImplementedError()


class InfluxDBMeasurementTagNode(InfluxDBMeasurementNode):
    """
    Stores an InfluxDB tag belonging to a specific measurement within a node.
    """

    def __init__(self, querier: InfluxDBQuerier, datasource_name: str,
                 measurement_name: str, tag: str):
        super().__init__(querier, datasource_name, measurement_name, tag, str)

    def tag(self):
        return self.column_name()

    def partial_measurement(self) -> InfluxDBMeasurement:
        return InfluxDBMeasurement(
            measurement_name=self.measurement_name(),
            tags={self.tag()},
            field_types={},
        )

    def result(self) -> 'InfluxDBMeasurementResult':
        return InfluxDBMeasurementResult(self, self.partial_measurement())


class InfluxDBMeasurementFieldNode(InfluxDBMeasurementNode):
    """
    Stores an InfluxDB measurement field within a node.
    """

    def __init__(self, querier: InfluxDBQuerier, datasource_name: str,
                 measurement_name: str, field: str, typeof: typing.Type):
        super().__init__(querier, datasource_name, measurement_name, field, typeof)

    def field(self):
        return self.column_name()

    def partial_measurement(self) -> 'InfluxDBMeasurement':
        return InfluxDBMeasurement(
            measurement_name=self.measurement_name(),
            tags=set(),
            field_types={self.field(): self.typeof()},
        )

    def result(self) -> 'InfluxDBMeasurementResult':
        return InfluxDBMeasurementResult(self, self.partial_measurement())


class InfluxDBResult(datagraph.Result, abc.ABC):
    """
    An abstract result for InfluxDB nodes.
    """

    def __init__(self, node: InfluxDBNode):
        super().__init__(node)
        self._cache = acache.InMemoryCache()

    def cache(self) -> acache.AbstractCache:
        return self._cache

    def is_same_datasource(self, other_node: datagraph.DataNode):
        node = self.node()
        assert isinstance(node, InfluxDBNode)
        return (
            isinstance(other_node, InfluxDBNode)
            and other_node.datasource_name() == node.datasource_name()
        )

    def constraints_from_node_values(self, ancestor_node_values: datagraph.NodeValues) \
            -> InfluxDBConstraint:
        """
        Given ancestor node values (node values within the current query path),
        returns an InfluxDBConstraint object that can be used to constrain the
        rows returned by a query.
        """
        tag_constraints = {}
        field_constraints = {}
        for ancestor_node, expected_value in ancestor_node_values.items():
            if not self.is_same_datasource(ancestor_node):
                continue

            if isinstance(ancestor_node, InfluxDBMeasurementFieldNode):
                field_constraints[ancestor_node.field()] = expected_value
            elif (isinstance(ancestor_node, InfluxDBMeasurementTagNode)
                  or isinstance(ancestor_node, InfluxDBSharedTagNode)):
                tag_constraints[ancestor_node.tag()] = expected_value
            else:
                assert False

        return InfluxDBConstraint(fields=field_constraints, tags=tag_constraints)

    def filter_values(self, column: str, constraints: InfluxDBConstraint,
                      values: CombinedRows) -> typing.Iterable[InfluxDBTypes]:
        """
        Filters the given rows and returns only the rows that match the
        constraints.

        The rows given may be grouped, such that the values are a list rather
        than a singular value. All of the values within a list are returned
        when the row matches the constraints.
        """
        for row_dict in values:
            if all(constraints.column_matches(k, v) for k, v in row_dict.items()):
                value = row_dict[column]
                if isinstance(value, list):  # See _combine_distinct_rows
                    yield from value
                else:
                    yield value

    @abc.abstractmethod
    def values(self, ancestor_node_values: typing.Optional[datagraph.NodeValues] = None) \
            -> typing.Iterable[InfluxDBTypes]:
        raise NotImplementedError()


class InfluxDBMeasurementResult(InfluxDBResult):
    """
    A result for InfluxDB nodes that queries and stores data from measurements, as
    opposed to just tag data (such as for InfluxDBSharedTagResult).
    """

    def __init__(self, node: InfluxDBMeasurementNode, measurement: InfluxDBMeasurement):
        super().__init__(node)
        self._measurement = measurement

    def join(self, other_node: datagraph.DataNode) -> datagraph.Result:
        node = self.node()
        assert isinstance(node, InfluxDBMeasurementNode)

        if not self.is_same_datasource(other_node):
            return other_node.result()

        if isinstance(other_node, InfluxDBSharedTagNode):
            # This is ok, so long as the tag is within this measurement. This
            # fact _should_ be encoded in the data graph with an edge, thus
            # we can assume this is true here.
            other_measurement = InfluxDBMeasurement(
                measurement_name=self._measurement.measurement_name(),
                tags={other_node.tag()},
                field_types={},
            )
        else:
            assert isinstance(other_node, InfluxDBMeasurementNode)
            other_measurement = other_node.partial_measurement()

        new_measurement = InfluxDBMeasurement.combine(self._measurement, other_measurement)
        return InfluxDBMeasurementResult(other_node, new_measurement)

    def _measurement_from_constraints(self, constraints: InfluxDBConstraint) \
            -> InfluxDBMeasurement:
        """
        Returns a new InfluxDBMeasurement with the current measurement combined
        with the tags and fields within the constraints.
        """
        new_tags = self._measurement.tags() | set(constraints.tags())
        new_field_types = self._measurement.field_types().copy()
        new_field_types.update(constraints.field_types())
        return InfluxDBMeasurement(
            measurement_name=self._measurement.measurement_name(),
            tags=new_tags,
            field_types=new_field_types,
        )

    @staticmethod
    def _combine_distinct_rows(measurement: InfluxDBMeasurement, rows: Rows) -> CombinedRows:
        """
        Combines rows where the tag values are the same. The result is that rows
        may contain values that are lists of values, where the values within the
        list are a union of all the row values where the tag values match.

        e.g. If a CPU measurement in the database has tags ('host', 'cpu'), but
             we are requesting CPU usage with just the host key, then the rows
             with the same host returned by the database need to be combined. In
             that case, the "cpu" and "cpu_usage" columns of the rows will have
             multiple values
        """
        distinct_tags = measurement.tags()

        # Each row will either contain a value, or a list of values if there
        # are multiple different values. This works since there is no list
        # type in InfluxDB.
        combined_rows = collections.defaultdict(dict)
        for row in rows:
            tag_values = tuple(row[tag] for tag in distinct_tags)
            prev_row_dict = combined_rows[tag_values]
            for key, value in row.items():
                if key not in prev_row_dict:
                    prev_row_dict[key] = value
                    continue

                if prev_row_dict[key] == value:
                    continue
                elif not isinstance(prev_row_dict[key], list):
                    prev_value = prev_row_dict[key]
                    prev_row_dict[key] = [prev_value, value]
                elif value not in prev_row_dict[key]:
                    prev_row_dict[key].append(value)

        # Note: Dictionaries are ordered by insertion; we use this to return
        #       values in the same order as given
        return list(combined_rows.values())

    def _values(self, constraints: InfluxDBConstraint) -> CombinedRows:
        node = self.node()
        assert isinstance(node, InfluxDBMeasurementNode)

        new_measurement = self._measurement_from_constraints(constraints)

        # Queries only work on fields, cannot select tags; See as_query()
        # for details
        if len(new_measurement.fields()) == 0:
            rows = node.querier().series(new_measurement.tags(), new_measurement.measurement_name())
        else:
            rows = node.querier().run_query(new_measurement.as_query())

        return self._combine_distinct_rows(new_measurement, rows)

    def values(self, ancestor_node_values: typing.Optional[datagraph.NodeValues] = None) \
            -> typing.Iterable[InfluxDBTypes]:
        if not ancestor_node_values:
            ancestor_node_values = {}

        node = self.node()
        assert isinstance(node, InfluxDBMeasurementNode)

        constraints = self.constraints_from_node_values(ancestor_node_values)
        column_name = node.column_name()
        cache_id = mangle_measurement_column_name(
            self._measurement.measurement_name(),
            "_".join(self._measurement.columns())
        )

        yield from self.filter_values(
            column_name,
            constraints,
            self._cache.retrieve_or_update(column_name, cache_id, self._values, constraints)
        )


class InfluxDBSharedTagResult(InfluxDBResult):
    """
    A result for InfluxDB nodes that queries and stores tags without regard
    to any measurement, as opposed to a measurement tag (such as for
    InfluxDBMeasurementResult).
    """

    def __init__(self, node: InfluxDBSharedTagNode, tags: typing.Set[str]):
        super().__init__(node)
        self._tags = tags

    def join(self, other_node: datagraph.DataNode) -> datagraph.Result:
        node = self.node()
        assert isinstance(node, InfluxDBSharedTagNode)

        if not self.is_same_datasource(other_node) or not isinstance(other_node, InfluxDBSharedTagNode):
            return other_node.result()

        return InfluxDBSharedTagResult(node, self._tags | {other_node.tag()})

    def _values(self, constraints: InfluxDBConstraint) -> Rows:
        node = self.node()
        assert isinstance(node, InfluxDBSharedTagNode)
        return node.querier().series(constraints.tags() | self._tags)

    def values(self, ancestor_node_values: typing.Optional[datagraph.NodeValues] = None) \
            -> typing.Iterable[InfluxDBTypes]:
        if not ancestor_node_values:
            ancestor_node_values = {}

        node = self.node()
        assert isinstance(node, InfluxDBSharedTagNode)

        constraints = self.constraints_from_node_values(ancestor_node_values)
        tag = node.tag()
        cache_id = "_".join(sorted(self._tags))

        yield from self.filter_values(
            tag,
            constraints,
            self._cache.retrieve_or_update(tag, cache_id, self._values, constraints)
        )


def extract_measurement_from_influxdb(querier: InfluxDBQuerier, measurement_name: str) \
        -> InfluxDBMeasurement:
    """
    Returns an InfluxDB measurement object for the given measurement name,
    extracted/queried from InfluxDB.
    """
    tags = querier.tags(measurement_name)
    field_types = querier.field_types(measurement_name)
    return InfluxDBMeasurement(
        measurement_name=measurement_name,
        tags=tags,
        field_types=field_types
    )


def extract_measurements_from_influxdb(querier: InfluxDBQuerier) -> typing.List[InfluxDBMeasurement]:
    """
    Returns a list of InfluxDB measurement objects for each measurement found
    in InfluxDB.
    """
    measurements = []
    for measurement_name in querier.measurement_names():
        measurement = extract_measurement_from_influxdb(querier, measurement_name)
        measurements.append(measurement)

    return measurements


def type_to_yaml_type_string(typeof: typing.Type) -> str:
    """
    Returns a string form of the given type.
    """
    for string, string_typeof in string_type_map.items():
        if string_typeof == typeof:
            return string
    assert False


def yaml_type_string_to_type(type_string: str) -> typing.Type:
    """
    Returns a type from the given string.
    """
    return string_type_map[type_string]


def format_yaml(querier: InfluxDBQuerier,
                measurements: typing.List[InfluxDBMeasurement]) -> str:
    # See from_yaml for the format here
    datasource_data = {
        "datasource": "influxdb",
        "target": querier.target(),
        "username": querier.username(),
        "password": querier.password(),
        "database": querier.database(),
        "proxy": querier.proxy(),
        "measurements": {
            measurement.measurement_name(): {
                "tags": list(measurement.tags()),
                "fields": {
                    field: type_to_yaml_type_string(field_type)
                    for field, field_type in measurement.field_types().items()
                },
            }
            for measurement in measurements
        }
    }
    return datagraph.dump_yaml("influxdb", datasource_data)


def node_name_from_yaml_identifier(yaml_identifier: str) -> str:
    # Measurements and tags/fields in YAML are identified by measurement.tag/field,
    # or simply tag if a shared tag
    if "." not in yaml_identifier:
        return yaml_identifier

    measurement_name, column_name = yaml_identifier.split(".", maxsplit=1)
    return mangle_measurement_column_name(measurement_name, column_name)


def from_yaml(datasource_name: str,
              datasource_data: dict,
              cache: typing.Optional[acache.AbstractCache] = None) -> InfluxDBDataGraph:
    #  datasource: influxdb
    #  target: localhost:8086
    #  username: influx
    #  password: youllneverevaguessthislol
    #  database: main
    #  proxy: socks5h://localhost:5555
    #  measurements:
    #    cpu_info:
    #      tags: [cluster, host, cpu]
    #      fields:
    #        user: float
    #        kernel: float
    #        disk: float
    #        vendor: str
    #        model: str
    #        freq: int
    #        max_freq: int
    #        is_thread: bool
    #        hexid: bytes
    assert datasource_data["datasource"] == "influxdb"

    target = datasource_data["target"]
    username = datasource_data["username"]
    password = datasource_data["password"]
    database = datasource_data["database"]
    proxy_or_none = datasource_data.get("proxy", None)
    querier = InfluxDBQuerier(
        host=target,
        username=username,
        password=password,
        database=database,
        proxy=proxy_or_none,
        cache=cache
    )

    measurements = []
    for measurement_name, measurement_data in datasource_data["measurements"].items():
        assert len(measurement_data["fields"]) > 0  # a measurement must have a field

        field_types = {}
        for field, field_type_string in measurement_data["fields"].items():
            field_types[field] = yaml_type_string_to_type(field_type_string)

        measurement = InfluxDBMeasurement(
            measurement_name=measurement_name,
            tags=set(measurement_data["tags"]),
            field_types=field_types
        )
        measurements.append(measurement)

    return InfluxDBDataGraph.graph_from_measurements(querier, datasource_name, *measurements)
