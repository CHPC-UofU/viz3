# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Defines a bunch of helper classes for creating color based on a range of values.

Author: Dylan Gardner, Robben Migacz
"""

from __future__ import annotations
import collections
import pkg_resources
import typing

from . import core


ColorWithOpacity = typing.Tuple[int,int,int,float]
ColorWithoutOpacity = typing.Tuple[int,int,int]
Color = typing.Union[ColorWithOpacity,ColorWithoutOpacity]


class InterpolatedColorRange:
    def __init__(self, min_value: float, max_value: float, start_rgb: Color, end_rgb: Color):
        self._value_range = (float(min_value), float(max_value))
        self._color_range = (core.RGBA(*map(int, start_rgb)), core.RGBA(*map(int, end_rgb)))

    def rgb_color(self, value: float):
        """
        Returns a color between the start and end colors, according to the
        fraction of the value in the value range.
        """
        fraction = max(
            0.0,
            min(
                1.0,
                (float(value) - self._value_range[0])
                / (self._value_range[1] - self._value_range[0]),
            ),
        )
        low_rgb, high_rgb = self._color_range
        new_r = int(low_rgb.r + (high_rgb.r - low_rgb.r) * fraction)
        new_g = int(low_rgb.g + (high_rgb.g - low_rgb.g) * fraction)
        new_b = int(low_rgb.b + (high_rgb.b - low_rgb.b) * fraction)
        return core.RGBA(new_r, new_g, new_b, 1.0)

    def rgb_min_color(self):
        return self._color_range[0]

    def rgb_max_color(self):
        return self._color_range[1]


class RedBlueColorRange(InterpolatedColorRange):
    def __init__(self, start_value: float, end_value: float, opacity: float = 1.0):
        red_rgb = (201, 42, 42, opacity)
        blue_rgb = (24, 100, 171, opacity)
        super().__init__(start_value, end_value, blue_rgb, red_rgb)


class BluePurpleColorRange(InterpolatedColorRange):
    def __init__(self, start_value: float, end_value: float, opacity: float = 1.0):
        blue_rgb = (181, 206, 220, opacity)
        purple_rgb = (213, 49, 255, opacity)
        super().__init__(start_value, end_value, blue_rgb, purple_rgb)


class OrangeRedColorRange(InterpolatedColorRange):
    def __init__(self, start_value: float, end_value: float, opacity: float = 1.0):
        red_rgb = (217, 72, 15, opacity)
        orange_rgb = (255, 244, 230, opacity)
        super().__init__(start_value, end_value, orange_rgb, red_rgb)


class OrangeRedLightColorRange(InterpolatedColorRange):
    def __init__(self, start_value: float, end_value: float, opacity: float = 1.0):
        red_rgb = (230, 106, 58, opacity)
        orange_rgb = (255, 252, 248, opacity)
        super().__init__(start_value, end_value, orange_rgb, red_rgb)


class GreenBlueColorRange(InterpolatedColorRange):
    def __init__(self, start_value: float, end_value: float, opacity: float = 1.0):
        green_rgb = (105, 219, 124, opacity)
        blue_rgb = (34, 139, 230, opacity)
        super().__init__(start_value, end_value, green_rgb, blue_rgb)


class GreenRedColorRange(InterpolatedColorRange):
    def __init__(self, start_value: float, end_value: float, opacity: float = 1.0):
        green_rgb = (81, 201, 48, opacity)
        red_rgb = (203, 50, 0, opacity)
        super().__init__(start_value, end_value, green_rgb, red_rgb)


class GreenRedDarkColorRange(InterpolatedColorRange):
    def __init__(self, start_value: float, end_value: float, opacity: float = 1.0):
        green_rgb = (55, 97, 43, opacity)
        red_rgb = (133, 58, 33, opacity)
        super().__init__(start_value, end_value, green_rgb, red_rgb)


color_name_map = {}
with open(pkg_resources.resource_filename("viz3", "static/colors.txt")) as f:
    for line in f.readlines():
        # e.g. blue1 5 5 5
        color_name, r, g, b = line.split()
        color_name_map[color_name] = core.RGBA(int(r), int(g), int(b))


def from_name(name: str, opacity: float = 1.0):
    color = color_name_map[name]
    color.opacity = opacity
    return color
