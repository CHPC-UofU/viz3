# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Contains a tree class.
"""
from __future__ import annotations
import typing

from . import core


# Some type annotations for the tree are missing here, simply because it's
# not straightforward to encode annotations for subclasses in a parent class
# and because I haven't bothered to look up how to do so...
# FIXME: This is somewhat of a duplicate data structure, since a similar API
#        is found with Node in the C++ core. We should export the C++ class!
class Tree:
    """
    An abstract tree with children that is iterable.
    """

    def __init__(self, name: str, parent):
        """
        An abstract notion of a tree.

        name: str
            The name of the tree node, or "" if root.
        parent: None or Tree
            A reference to the parent node, or None if root.
        """
        self._name = name
        if name != "":
            assert parent is not None
        else:
            assert parent is None

        self._parent = parent
        self._children: typing.List[Tree] = []

    def name(self) -> str:
        """
        The name of the node.
        """
        return self._name

    def parent(self):
        """
        A reference to the parent Tree node.
        """
        return self._parent

    def is_root(self) -> bool:
        """
        Whether this is the root node.
        """
        return self.parent() is None

    def has_children(self) -> bool:
        """
        Returns whether this node has any children nodes.
        """
        return len(self._children) == 0

    def find_descendant(self, with_path: core.Path):
        """
        Returns a descendant node with the given path or raises IndexError if
        no such descendant exists.
        """
        for child_node in self._children:
            if child_node.name() != with_path.first():
                continue

            if with_path.is_leaf():
                return child_node

            return child_node.find_descendant(with_path.without_first())

        if with_path.is_leaf() and self.name() == with_path.first():
            return self

        raise IndexError("Could not find descendant with path {}".format(with_path))

    def path(self) -> core.Path:
        """
        Returns a viz3.Path() to this node in the tree.
        """
        if self.is_root():
            return core.Path()
        return self.parent().path() + self.name()  # type: ignore

    def _children_names(self) -> typing.List[str]:
        """
        Returns a list of children names. Should only be used
        by subclasses.
        """
        return [child.name() for child in self._children]

    def _add_child(self, new_child):
        """
        Adds a new child node to this node. Should only be used
        by subclasses.
        """
        assert not any(child.name() == new_child.name() for child in self._children)
        assert self != new_child
        self._children.append(new_child)
        return new_child

    def _replace_child(self, replacing_child):
        """
        Replaces a child node in this node. Should only be used
        by subclasses.
        """
        name = replacing_child.name()
        for i, child in enumerate(self._children):
            if child.name() == name:
                self._children[i] = replacing_child
                return
        raise ValueError("Tried to replace non-existent child!")

    def _get_child(self, child_name: str):
        """
        Returns a child node of this node. Should only be used
        by subclasses.
        """
        for child in self._children:
            if child.name() == child_name:
                return child
        raise IndexError("Could not find child with name: " + child_name)

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._children[item]
        elif isinstance(item, Tree):
            return self._children.index(item)
        elif isinstance(item, str):
            return self._get_child(item)
        else:
            raise TypeError("Indexes into a subtree must be either a integer, "
                            "Tree, or a string.")

    def __iter__(self):
        for child in self._children.copy():
            assert child != self
            yield child
