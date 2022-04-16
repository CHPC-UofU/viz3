# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
A helper module used across viz3.
"""

from __future__ import annotations
import typing
import re

from . import core


def class_name(cls: type):
    """
    Returns the name of the given class.
    """
    try:
        obj_name = cls.__name__
    except AttributeError:
        # for some reason not all objects in Python have __name__, I
        # dunno why, so this is a dirty hack that someone more
        # knowledgable should fix....
        # FIXME: Replace this hack with something better
        match_or_none = re.match(r"<class '(\S+)'>", str(type(cls)))
        if not match_or_none:
            obj_name = str(type(cls))
        else:
            obj_name = match_or_none.group(1)
    return obj_name


def swap_yz_coords(coord: core.Point):
    """
    Swaps the y and z components of the given coord and returns the coord
    as a tuple.

    Why this? Well um so I didn't know that "y" does not necessarily mean
    height in 3d and "z" may actually be the height when originally writing
    the viz3 library, so we have to reinterpret things here...
    """
    return coord.x, coord.z, coord.y


# Path() can store a DataTree path, or a LayoutEngine path; help the programmer
# slightly by adding an alias here.
LayoutPath = typing.NewType("LayoutPath", core.Path)
AttributeMap = typing.Dict[str, str]
