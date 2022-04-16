# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Defines a series of value transformations used when applying data from
data nodes (in the DataGraph) to LayoutEngine element attributes.
"""
import typing

from . import colors


class TransformationError(Exception):
    pass


TransformationFunc = typing.Callable[[typing.Any], typing.Any]
TransformationFuncMap = typing.Dict[str, TransformationFunc]


def _pct_color_range(fractional_value: float, color_range_ctor=colors.RedBlueColorRange):
    color_range = color_range_ctor(0.0, 1.0)
    return [color_range.rgb_color(fractional_value)]


def _to_orange_red_color(fractional_value: float):
    color = _pct_color_range(fractional_value, color_range_ctor=colors.OrangeRedColorRange)
    return color


def _to_green_blue_color(fractional_value: float):
    color = _pct_color_range(fractional_value, color_range_ctor=colors.GreenBlueColorRange)
    return color


def _fraction(first_value, second_value):
    if second_value == 0:
        return [second_value]  # maintaining type of original (== 0 ignores type)
    return [first_value / second_value]


def _pct(first_value, second_value):
    return [_fraction(first_value, second_value)[0] * 100]


def _nop(value):
    return [value]


def _sum(*args):
    return [sum(args)]


def _div_by_mib(value):
    return [value / (1024 * 16)]


def _times_two(value):
    return [value * 5]


def default_transformations():
    return {
        "pct_color_range": _pct_color_range,
        "to_red_blue": _pct_color_range,
        "to_orange_red": _to_orange_red_color,
        "to_green_blue": _to_green_blue_color,
        "fraction": _fraction,
        "sum": _sum,
        "pct": _pct,
        "nop": _nop,
        "div_by_mib": _div_by_mib,
        "times_two": _times_two,
    }
