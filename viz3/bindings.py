# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Contains classes for storing a mapping between data queries (targeting the
data graph) and layout engine nodes (containing Element()s of the
LayoutEngine).
"""

from __future__ import annotations
import dataclasses
import re
import typing

from . import core
from . import transformation as tr
from . import tree
from . import utils
from . import lang


class BindingError(Exception):
    pass


SubBindingId = int


class AttributeBinding:
    """
    Stores a mapping between an layout Element attribute and a data graph
    query, with additional transformations.
    """

    def __init__(self, value_langs: typing.List[lang.ValueLanguage], attribute: str):
        self._langs = value_langs
        self._attribute = attribute

    def data_paths(self) -> typing.List[core.Path]:
        return [lang.path() for lang in self._langs]

    def subbinding_data_paths(self) -> typing.Dict[SubBindingId, core.Path]:
        return {i: lang.path() for i, lang in enumerate(self._langs)}

    def attribute(self) -> str:
        return self._attribute

    def _formatted_value(self, lang: lang.ValueLanguage, value: typing.Any) -> str:
        if isinstance(value, float):
            value = round(value, 2)

        return lang.formatted_value(str(value))

    def apply_default(self, binding_id: SubBindingId) -> str:
        lang = self._langs[binding_id]
        default_value = lang.default()
        if default_value is None:
            raise ValueError("NULL value with binding {} given to transform, "
                             "but no default to fallback on".format(lang))
        return default_value

    def apply_transformations(self, binding_id: SubBindingId,
                              values: typing.List[typing.Any],
                              tr_func_map: tr.TransformationFuncMap) -> str:
        assert None not in values

        lang = self._langs[binding_id]
        for tr_name in lang.pipeline():
            tr_func = tr_func_map.get(tr_name, None)
            if tr_func is None:
                raise tr.TransformationError(
                    "Transformation '{}' requested is not registered!".format(tr_name)
                )
            try:
                values = tr_func(*values)
            except Exception as err:
                raise tr.TransformationError("Failed to transform values {}: {}".format(values, err))

        try:
            if len(values) > 1:
                raise tr.TransformationError(
                    "Transformation pipeline '{}' does not return a single value!"
                    .format(str(self))
                )
        except TypeError:
            raise tr.TransformationError(
                "Transformation pipeline '{}' returned a '{}', rather than items "
                "contained in a list! (Transformations return a list of values "
                "processed by the following transformation; the last "
                "transformation should return a single item in a list)"
                .format(str(self), values)
            )

        return self._formatted_value(lang, values[0])

    def combined_values(self, values: typing.List[str]) -> str:
        return "".join(map(str, values))

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return "{}='{}'".format(self._attribute, "".join(map(str, self._langs)))


@dataclasses.dataclass
class BindingFilter:
    data_path: core.Path
    selector: typing.Set[typing.Optional[str]]
    is_negative: bool
    is_regex: bool

    def does_match_null(self) -> bool:
        return None in self.selector

    def should_keep(self, instance) -> bool:
        if self.is_regex:
            does_match = any(re.search(exp, instance) is not None for exp in self.selector)
        else:
            does_match = instance in self.selector

        return not does_match if self.is_negative else does_match

    def __repr__(self) -> str:
        string = str(self.data_path)
        if self.selector:
            string += "!" if self.is_negative else ""
            string += "={" + ", ".join(s if s is not None else "null" for s in self.selector) + "}"
        return string

    def __str__(self) -> str:
        return self.__repr__()


class Binding:
    """
    Stores a mapping between a data node in a DataTree and a LayoutEngine node.
    """

    def __init__(self, layout_path: utils.LayoutPath,
                 data_lang: lang.BindLanguage,
                 attr_bindings: typing.List[AttributeBinding],
                 binding_filter: typing.Optional[BindingFilter] = None,
                 limit: typing.Optional[int] = None):
        self._layout_path = layout_path
        self._data_lang = data_lang
        assert all(isinstance(attr_binding, AttributeBinding) for attr_binding in attr_bindings)
        self._attr_bindings = attr_bindings
        self._filter = binding_filter
        self._limit = limit

    def attr_bindings(self) -> typing.List[AttributeBinding]:
        """
        Returns all the LayoutEngine Node attribute bindings.
        """
        return self._attr_bindings.copy()

    def has_filter(self) -> bool:
        return self.filter() is not None

    def filter(self) -> typing.Optional[BindingFilter]:
        return self._filter

    def filter_data_path(self):
        return self._filter

    def matches_null(self):
        return self.has_filter() and self.filter().does_match_null()

    def keep_when_filtered_out(self):
        return self._data_lang.keep_when_filtered_out()

    def limit(self) -> typing.Optional[int]:
        return self._limit

    def data_path(self) -> core.Path:
        return self._data_lang.path()

    def layout_path(self) -> utils.LayoutPath:
        return self._layout_path

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return "Binding({} -> Data: {}, keep_when_filtered_out? {}, attr_bindings=[{}], filter={})".format(
            str(self.layout_path()),
            str(self.data_path()),
            str(self._data_lang.keep_when_filtered_out()),
            self._attr_bindings,
            self.filter()
        )


class BindingTree(tree.Tree):
    """
    A binding tree simply stores bindings (mapping between a LayoutEngine node
    and a data node) in a hierarchy that reflects the hierarchy of bindings
    within the LayoutEngine.
    """

    def __init__(self, binding: Binding, parent: BindingTree):
        if not binding:
            name = ""
        else:
            name = str(binding.layout_path()).replace(".", "-")

        super().__init__(name, parent)
        self._binding = binding

    @classmethod
    def create_root(cls):
        return cls(None, None)  # type: ignore

    def binding(self) -> Binding:
        return self._binding

    def walk_data_paths(self) -> typing.Iterator[core.Path]:
        """
        Yields all data paths in this tree in the order defined by the
        bindings.
        """
        if not self.is_root():
            binding = self.binding()

            yield binding.data_path()
            for attr_binding in binding.attr_bindings():
                yield from attr_binding.data_paths()

            if binding.has_filter():
                assert binding.filter()
                yield binding.filter().data_path

        for child_binding_node in self:
            yield from child_binding_node.walk_data_paths()

    def _construct_child(self, binding: Binding) -> BindingTree:
        child_node = BindingTree(binding, self)
        return self._add_child(child_node)

    def construct_subbinding(self, layout_path: utils.LayoutPath, data_lang: lang.BindLanguage,
                             attr_bindings: typing.List[AttributeBinding],
                             binding_filter: typing.Optional[BindingFilter] = None,
                             limit: typing.Optional[int] = None) \
            -> BindingTree:
        """
        Creates a sub-node with an element binding.
        """
        binding = Binding(layout_path, data_lang, attr_bindings, binding_filter, limit)
        child_node = self._construct_child(binding)
        assert child_node != self
        return child_node
