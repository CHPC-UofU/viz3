# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Defines a module that parses XML into a LayoutEngine.
"""

from __future__ import annotations
import inspect
import sys
import typing

import lxml
import lxml.etree

from . import bindings
from . import core
from . import lang
from . import utils


# lxml may be swapped out later; add alias to make migration easier
XMLNode = typing.Type[lxml.etree._ElementTree]
XMLElement = typing.Type[lxml.etree.Element]


def _lookup_element_constructor(name: str) -> type:
    """
    Returns a Python viz3 element constructor for the given name. Name
    managling occurs such that the full class name need not be specified. If
    no class can be found with the given name, None is returned.

    >>> _lookup_element_constructor("element")
    Element
    >>> _lookup_element_constructor("box")
    BoxElement
    >>> _lookup_element_constructor("Grid")
    GridLayoutElement
    """
    is_element_class = lambda m: inspect.isclass(m) and (m.__name__.endswith("Element") or m.__name__.endswith("Layout"))

    classes = inspect.getmembers(sys.modules["viz3.core"], is_element_class)
    for cls_name, cls in classes:
        element_name = cls_name
        if element_name.endswith("Layout"):
            element_name = element_name[:-len("Layout")]
        if element_name.endswith("Element"):
            element_name = element_name[:-len("Element")]

        if element_name.lower() == name.lower():
            return cls

    raise bindings.BindingError("Element constructor could not be found for {}".format(name))


def _pop_and_retrieve_attribute_bindings(element_path: core.Path,
                                         attribute_dict: typing.Dict[str, str]) \
        -> typing.List[bindings.AttributeBinding]:
    """
    Given a dictionary of XML attributes, returns a list of attribute bindings.
    """
    attr_bindings = []
    for attr, content in attribute_dict.copy().items():
        try:
            val_lang = lang.ValueLanguage.from_string(content, element_path)
            attribute_dict.pop(attr)
            attr_bindings.append(bindings.AttributeBinding(val_lang, attr))
        except lang.LanguageSyntaxError:
            pass

    return attr_bindings


def _try_pop_and_retrieve_filter(element_path: core.Path,
                                 attribute_dict: typing.Dict[str, str]) \
        -> typing.Optional[bindings.BindingFilter]:
    """
    Given a dictionary of XML attributes, returns the filters to apply, or None
    if there is no filter. See _looks_like_value_language for what is a value
    language that gets returned as a binding.
    """
    filter_str_or_none = attribute_dict.pop("filter", None)
    if filter_str_or_none is None:
        return None

    val_lang = lang.FilterLanguage.from_string(filter_str_or_none, element_path)
    return bindings.BindingFilter(val_lang.path(), val_lang.selector(), val_lang.is_negative(), val_lang.is_regex())


def _unique_name_from_xml_element(xml_node: XMLElement) -> str:
    """
    Returns a unique name for the given XML node.
    """
    name = xml_node.tag
    parent_node_or_none = xml_node.getparent()
    if parent_node_or_none is not None:
        name += str(parent_node_or_none.index(xml_node))
    return name


def _create_element(tag: str, name: str, attributes: typing.Dict[str, typing.Any]):
    ctor = _lookup_element_constructor(tag)
    try:
        return ctor(name, attributes)
    except TypeError as err:
        raise bindings.BindingError("Tried to bind an invalid attribute to <{} "
                                    "name=\"{}\">: {}".format(tag, name, str(err)))


def _create_layout_node_from_xml(layout_node: core.Node, xml_parent: XMLElement,
                                 binding_tree: bindings.BindingTree,
                                 ancestor_data_path: typing.Optional[core.Path] = None):
    # copy since <include> elements insert children nodes
    i_fixup = 0
    for i, xml_child in enumerate(list(xml_parent)):
        tag = xml_child.tag  # e.g. 'juxtapose' of <juxapose>
        if not isinstance(tag, str):  # skip comments, and other XML weirdness
            continue

        attributes = dict(xml_child.attrib.items())  # .e.g <... name="foo"> -> {"name": "foo"}
        name = attributes.pop("name", _unique_name_from_xml_element(xml_child))
        # path looks like attribute binding, so pop now so func doesn't get confused

        data_bind_text = attributes.pop("bind", None)
        if data_bind_text is not None:
            data_bind_lang = lang.BindLanguage.from_string(data_bind_text, ancestor_data_path)
            data_bind_path = data_bind_lang.path()
        else:
            data_bind_lang = None
            data_bind_path = ancestor_data_path if ancestor_data_path is not None else core.Path()

        # Pop here, since _pop_and_retrieve_attribute_bindings might interpret the
        # path as an attribute binding if the path has no slashes
        include_path_or_none = attributes.pop("path", None)
        limit = int(attributes["limit"]) if "limit" in attributes else None
        binding_filter_or_none = _try_pop_and_retrieve_filter(data_bind_path, attributes)
        attr_bindings = _pop_and_retrieve_attribute_bindings(data_bind_path, attributes)
        if len(attr_bindings) > 0 and data_bind_lang is None:
            # If someone does text="Usage: .usage bytes", but leaves out the
            # bind="..." part, use the ancestor binding (since that is
            # presumably what the attribute bindings are relative to)
            data_bind_lang = lang.BindLanguage(data_bind_path)

        if tag == "include":
            if include_path_or_none is None:
                raise ValueError("No 'path' attribute for include element!")

            i_fixup += _insert_subxml_into_parent(include_path_or_none, i + i_fixup, xml_child)
            _create_layout_node_from_xml(layout_node, xml_child, binding_tree, ancestor_data_path)
            continue

        element = _create_element(tag, name, attributes)

        if data_bind_lang is not None:
            layout_node_child = layout_node.construct_template(element)
            layout_child_path = utils.LayoutPath(layout_node_child.path())
            child_binding_tree = binding_tree.construct_subbinding(
                layout_child_path,
                data_bind_lang,
                attr_bindings,
                binding_filter_or_none,
                limit,
            )
        else:
            child_binding_tree = binding_tree
            layout_node_child = layout_node.construct_child(element)

        _create_layout_node_from_xml(layout_node_child, xml_child, child_binding_tree, data_bind_path)
        i += 1


def _insert_subxml_into_parent(sub_xml_filepath: str, i: int, parent_xml_node: XMLElement) -> XMLElement:
    subxml_tree = lxml.etree.parse(sub_xml_filepath)
    subxml_root = subxml_tree.getroot()
    subxml_children = list(subxml_root)
    for child_index, subxml_child in enumerate(subxml_children):
        parent_xml_node.insert(i + child_index, subxml_child)

    assert all(new_xml_child.getparent() == parent_xml_node for new_xml_child in parent_xml_node)
    return len(subxml_children)


def _read_xml(xml_filepath: str) -> XMLElement:
    # We are using lxml here, since unlike xml.etree.ElementTree, iterating over
    # subnodes can be done in document order!
    xml_tree = lxml.etree.parse(xml_filepath)
    xml_root = xml_tree.getroot()
    if xml_root.tag != "visualization":
        raise bindings.BindingError("XML tree does not start with a <visualization> tag!")
    return xml_root


def from_xml(xml_filepath: str) -> typing.Tuple[core.LayoutEngine, bindings.BindingTree]:
    """
    Returns a core.LayoutEngine() tree from the given XML file.
    """
    xml_root = _read_xml(xml_filepath)
    layout_engine = core.LayoutEngine()
    tx = layout_engine.transaction()
    layout_root = tx.node()

    binding_tree = bindings.BindingTree.create_root()
    _create_layout_node_from_xml(layout_root, xml_root, binding_tree)

    tx.render()
    return layout_engine, binding_tree
