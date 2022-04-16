# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
User-facing module that contains the Visualization class for creating
visualizations, as well as the business logic of taking data from the data
graph and mapping that onto "templates" of 3D LayoutEngine nodes.
"""
from __future__ import annotations

import collections
import typing
import logging

from . import transformation as tr
from . import bindings
from . import core
from . import datagraph
from . import from_xml
from . import utils

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def mangle_value_into_path_part(value: typing.Any):
    if value is None:
        return "null"
    return str(value).replace(".", "_").replace(" ", "__").replace(":", "_port_")


class DynamicVisualization:

    def __init__(self, layout_engine: core.LayoutEngine, data_graph: datagraph.DataGraph, binding_tree: bindings.BindingTree):
        """
        Defines a visualization that updates a renderer when the data graph is
        updated via this object's .update() function.
        """
        self._layout_engine = layout_engine
        self._data_graph = data_graph
        self._binding_tree = binding_tree
        self._transformation_map = tr.default_transformations()

    def add_transformation(self, name: str, transformation_func: tr.TransformationFunc):
        """
        Adds a transformation function that manipulates an attribute value.
        """
        if name in self._transformation_map:
            raise ValueError("Transformation {} was already added!".format(name))
        self._transformation_map[name] = transformation_func

    def layout_engine(self):
        return self._layout_engine

    @staticmethod
    def from_xml(yaml_filepath: str, xml_viz_filepath: str) -> DynamicVisualization:
        """
        Creates a visualization from a LayoutEngine hierarchy defined in XML,
        with each XML element optionally binding to data queries in the given
        data  graph. For each binding, a template node in the LayoutEngine
        tree is created, and for each non-bound XML element a regular child
        node is created. When this visualization is updated, the template
        nodes are "exploded" into non-templated nodes to produce the current
        iteration of the visualization.

        e.g. A flat data graph '.machine.cpus.usage', where .machine returns
             hostnames, .machine.cpus returns CPU cores for the given hostname,
             and .machine.cpus.usage returns per-core usage.

             A viz3 XML file might contain the following:

             <juxtapose name="motherboards" axis="x">
                 <juxtapose name="motherboard" bind=".machine" spacing="10">
                    <plane name="socket" padding="1"/>
                     <grid name="cpus" spacing="2">
                         <box name="cpu" bind=".machine.cpus" width="10" height="2" depth="10"/>
                     </grid>
                 </juxtapose>
             </juxtapose>

             which visualizes a CPU socket split into cores.
        """
        layout_engine, binding_tree = from_xml.from_xml(xml_viz_filepath)
        data_graph = datagraph.from_yaml_file(yaml_filepath)
        return DynamicVisualization(layout_engine, data_graph, binding_tree)

    def update(self, constraints: typing.Optional[typing.Dict[str, str]] = None):
        """
        Updates the visualization based on changes to the data graph.
        """
        if constraints is None:
            constraints = {}

        tx = self.layout_engine().transaction()
        root_node = tx.node()
        self._reexplode_layout_engine(root_node, constraints)
        tx.render()

    def _reexplode_layout_engine(self, root_node: core.Node, constraints: typing.Dict[str, str]):
        """
        "Explodes" the bound LayoutEngine nodes into many duplicate nodes for
        each unique instance found between each bound data graph node and the
        node's parent bound data graph node. Any attribute bindings (element
        attributes bound to a data value) are also updated.

        When the child data path found in a binding is a descendant of the parent
        binding's data graph path, the result is a constrained explosion in the
        child (constrained by the instances of the parent).

        Use of the former logic makes it convenient to add detail in sub-layouts
        of the visualization tree that is tied to sub-data-groups or values.

        For example (in XML):
          <juxtapose>
            <grid bind=".datacenter">
              <box bind=".datacenter.rack.machine.cpu" text="CPU: .cpu">
            </grid>
          </juxtapose>

        with two datacenters (DDC and INSCC), two machines (h11, h12) in DDC in
        rack 1 and 2, three machines in INSCC (h21, h22, h23) in rack 3, and
        2 cores per machine would result in the following "exploded"
        visualization tree:
          <juxtapose>
            <grid text="ddc">
              <box text="h11">
              <box text="h11">
              <box text="h12">
              <box text="h12">
            </grid>
            <grid text="inscc">
              <box text="h21">
              <box text="h21">
              <box text="h22">
              <box text="h22">
              <box text="h32">
              <box text="h32">
            </grid>
          </juxtapose>
        """
        logger.info("Exploding layout tree")
        for binding, resolved_layout_path, attribute_map in self._walk(constraints):
            instance = resolved_layout_path.last()
            template_name = binding.layout_path().last()
            parent_of_bound_node = root_node.find_descendant(resolved_layout_path.without_last())

            if not parent_of_bound_node.has_child(instance):
                logger.debug("Making template %s with instance %s", template_name, instance)
                bound_node = parent_of_bound_node.try_get_child_or_make_template(template_name, instance)
            else:
                bound_node = parent_of_bound_node.try_get_child(instance)

            assert bound_node is not None
            logger.debug("Updating element %s with map %s", bound_node.element, attribute_map)
            bound_node.element.update_from_attributes(attribute_map)

    def _walk(self, constraints: typing.Dict[str, str]) \
            -> typing.Iterable[typing.Tuple[bindings.Binding, core.Path, utils.AttributeMap]]:
        result_graph = datagraph.ResultGraph.from_paths(
            self._data_graph,
            self._binding_tree.walk_data_paths()
        )

        # FIXME: This should be handled by creating a FilterLangugage, allowing
        #        further flexibility. It should also be processed somewhere
        #        else than here...
        ancestor_node_values = {}
        for mangled_name, expected_value in constraints.items():
            ancestor_node_values[self._data_graph.find_with_mangled_name(mangled_name)] = expected_value

        yield from self._walk_impl(self._binding_tree, core.Path(), ancestor_node_values, result_graph)

    def _walk_impl(self, parent_binding_node: bindings.BindingTree,
                   parent_resolved_layout_path: core.Path,
                   ancestor_node_values: datagraph.NodeValues,
                   result_graph: datagraph.ResultGraph) \
            -> typing.Iterable[typing.Tuple[bindings.Binding, core.Path, utils.AttributeMap]]:
        """
        Yields bindings, their corresponding path in the final layout tree,
        and a map of attribute values to update the element with.
        """
        # Yes, this is an ugly function. I do not currently know how to do
        # better, since we need to simultaneously walk a binding tree and
        # execute queries that are constrained by parent and ancestor binding
        # query results.
        #
        # Regardless, the way we do this is also problematic from an efficency
        # standpoint: we query each binding N times, where N is the number of
        # instances returned by the parent query, rather than querying each
        # binding once per declartion. This leads to a combinatorial number of
        # queries, which is slightly improved by the fact that we cache query
        # values in each result, but nevertheless, this is slower than it
        # should be.
        # FIXME: ^ See above
        if parent_binding_node.is_root():
            parent_layout_path = core.Path()
        else:
            parent_layout_path = parent_binding_node.binding().layout_path()  # type: ignore

        for child_binding_node in parent_binding_node:
            child_binding = child_binding_node.binding()
            child_data_path = child_binding.data_path()
            logger.info("Processing bindings of %s (%s)", child_data_path, child_binding.layout_path())

            intermediate_layout_path = (child_binding.layout_path() - parent_layout_path)
            seen_values = collections.defaultdict(lambda: 0)

            result = result_graph.result(child_data_path)
            node = result.node()
            node_values = self._query_values(child_binding, result, ancestor_node_values)

            def resolve_layout_path(_value: typing.Optional[typing.Any] = None):
                value_path_part = mangle_value_into_path_part(_value)
                seen_values[value_path_part] += 1
                return (
                    parent_resolved_layout_path
                    + intermediate_layout_path.without_last()
                    + (intermediate_layout_path.last()
                       + "_" + value_path_part
                       + "_" + str(seen_values[value_path_part]))
                )

            def apply_value_to_binding(_value, _was_not_filtered_out):
                _new_ancestor_node_values = ancestor_node_values.copy()
                # If the element binding fails, but keep_when_filtered_out was
                # True or the binding matches null
                if _value is not None:
                    in_null_binding = False
                    _new_ancestor_node_values[node] = _value
                    for _adaptor in self._data_graph.adaptors_from(node):
                        _new_ancestor_node_values[_adaptor.adapt_node(node)] = _adaptor.adapt_value(_value)
                else:
                    in_null_binding = True

                _is_filtered_out = self._check_if_filtered_out(
                    child_binding,
                    _new_ancestor_node_values,
                    result_graph,
                    in_null_binding,
                )
                if _is_filtered_out:
                    logger.debug("%s with %s got filtered out", node, _value)
                    _was_not_filtered_out[0] = False
                    return

                _has_missing_values, _attribute_map = self._query_attribute_bindings(
                    child_binding.attr_bindings(),
                    _new_ancestor_node_values,
                    result_graph,
                    in_null_binding,
                )
                if _has_missing_values:
                    logger.debug("%s with %s got filtered out due to missing attribute values", node, _value)
                    _was_not_filtered_out[0] = False
                    return

                _resolved_layout_path = resolve_layout_path(_value)
                yield child_binding, _resolved_layout_path, _attribute_map
                yield from self._walk_impl(
                    child_binding_node,
                    _resolved_layout_path,
                    _new_ancestor_node_values,
                    result_graph,
                )
                _was_not_filtered_out[0] = True
                return

            logger.debug("Got %s (%s) values %s", node, child_binding, node_values)
            was_not_filtered_out_param = [True]
            any_values_matched = False
            for node_value in node_values:
                # Cannot return a value from a iterator after done, so this is
                # my hack for an out parameter. We could collect the values,
                # but with large subtrees that forces the tree to be built all
                # at once at the end, which harms debugability.
                yield from apply_value_to_binding(node_value, was_not_filtered_out_param)
                any_values_matched |= was_not_filtered_out_param[0]

            if not any_values_matched and child_binding.keep_when_filtered_out():
                logger.debug("Continuing %s despite being filtered out", node)
                yield from apply_value_to_binding(None, [None])

    @staticmethod
    def _query_values(binding: bindings.Binding,
                      result: datagraph.Result,
                      ancestor_node_values: datagraph.NodeValues) -> typing.List[typing.Any]:
        node_values = list(result.values(ancestor_node_values))
        if binding.matches_null():
            if len(node_values) == 0:
                node_values = [None]
            else:
                node_values = []

        return node_values[:binding.limit()]

    @staticmethod
    def _query_attribute_binding(attr_binding: bindings.AttributeBinding,
                                 ancestor_node_values: datagraph.NodeValues,
                                 result_graph: datagraph.ResultGraph,
                                 in_null_binding: bool,
                                 tr_map: tr.TransformationFuncMap) -> typing.Any:
        values = []
        for binding_id, attr_data_path in attr_binding.subbinding_data_paths().items():
            try:
                if in_null_binding:
                    value = attr_binding.apply_default(binding_id)
                else:
                    result = result_graph.result(attr_data_path)
                    result_values = list(result.values(ancestor_node_values))
                    if not result_values:
                        # This might fail if no default is set
                        value = attr_binding.apply_default(binding_id)
                    else:
                        value = attr_binding.apply_transformations(binding_id, result_values,
                                                                   tr_func_map=tr_map)

                assert value is not None and value != "None"
                values.append(value)

            except Exception as err:
                raise ValueError("Failed to get attribute bindings for {} (with ancestor values {}): {}".format(
                    attr_data_path,
                    ancestor_node_values,
                    str(err))
                )

        return attr_binding.combined_values(values)

    def _query_attribute_bindings(self, attr_bindings: typing.List[bindings.AttributeBinding],
                                  ancestor_node_values: datagraph.NodeValues,
                                  result_graph: datagraph.ResultGraph,
                                  in_null_binding: bool) \
            -> typing.Tuple[bool, utils.AttributeMap]:
        attribute_map = {}
        for attr_binding in attr_bindings:
            try:
                value = self._query_attribute_binding(attr_binding, ancestor_node_values, result_graph,
                                                      in_null_binding, self._transformation_map)
            except ValueError as err:
                logger.debug("Transformation on %s failed: %s", attr_binding, err)
                return True, {}
            except tr.TransformationError as err:
                raise RuntimeError("Failed to get attribute bindings for {} (with ancestor values {}): {}".format(
                    attr_binding,
                    ancestor_node_values,
                    str(err))
                )

            attribute_map[attr_binding.attribute()] = value

        return False, attribute_map

    @staticmethod
    def _check_if_filtered_out(binding: bindings.Binding,
                               ancestor_node_values: datagraph.NodeValues,
                               result_graph: datagraph.ResultGraph,
                               in_null_binding: bool) -> bool:
        if not binding.has_filter() or in_null_binding:
            return False

        binding_filter = binding.filter()
        result = result_graph.result(binding_filter.data_path)
        values = list(result.values(ancestor_node_values))
        logger.debug("Got values for filter %s: %s", binding_filter, values)
        if len(values) == 0:
            return not binding_filter.does_match_null()

        return not any(binding_filter.should_keep(str(value)) for value in values)
