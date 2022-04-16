// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <algorithm>
#include <ostream>
#include <string>
#include <cassert>

#include "value_types.hpp"

const char* axis_string(Axis axis)
{
    switch (axis) {
    case Axis::X:
        return "x";
    case Axis::Y:
        return "y";
    case Axis::Z:
        return "z";
    default:
        assert(false);
    }
}

Axis string_to_axis(const std::string_view& string)
{
    std::string str { string };
    std::transform(str.begin(), str.end(), str.begin(), ::tolower);
    if (str == "x")
        return Axis::X;
    else if (str == "y")
        return Axis::Y;
    else if (str == "z")
        return Axis::Z;

    throw std::invalid_argument("Axis given is not X, y, nor z!");
}

Axis opposite_axis(Axis axis)
{
    switch (axis) {
    case Axis::X:
        return Axis::Z;
    case Axis::Y:
        return Axis::X;
    case Axis::Z:
        return Axis::X;
    default:
        assert(false);
    }
}

std::ostream& operator<<(std::ostream& os, const Axis& axis)
{
    os << axis_string(axis);
    return os;
}

std::ostream& operator<<(std::ostream& os, const Alignment& align)
{
    os << alignment_string(align);
    return os;
}

const char* alignment_string(Alignment align)
{
    switch (align) {
    case Alignment::Left:
        return "left";
    case Alignment::Center:
        return "center";
    case Alignment::Right:
        return "right";
    default:
        assert(false);
    }
}

Alignment string_to_alignment(const std::string_view& string)
{
    std::string str { string };
    std::transform(str.begin(), str.end(), str.begin(), ::tolower);
    if (str == "left")
        return Alignment::Left;
    else if (str == "center")
        return Alignment::Center;
    else if (str == "right")
        return Alignment::Right;

    throw std::invalid_argument("Alignment given is not left, center, or right!");
}
