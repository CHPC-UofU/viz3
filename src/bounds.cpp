// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <cmath>
#include <ostream>
#include <tuple>

#include "bounds.hpp"
#include "coords.hpp"
#include "rotation.hpp"

namespace viz3 {

std::ostream& operator<<(std::ostream& os, const Bounds& bounds)
{
    os << "{" << bounds.base() << ", " << bounds.end() << "}";
    return os;
}


Bounds Bounds::strip_pos()
{
    auto [x_length, y_length, z_length] = lengths();
    return { Point(), Point(x_length, y_length, z_length) };
}

std::tuple<float, float, float> Bounds::lengths() const
{
    auto diff_coord = (m_coords.second - m_coords.first);
    return { std::abs(diff_coord.x), std::abs(diff_coord.y), std::abs(diff_coord.z) };
}

float Bounds::axis_length(Axis axis) const
{
    switch (axis) {
    case Axis::X:
        return width();
    case Axis::Y:
        return height();
    case Axis::Z:
        return depth();
    }

    assert(false);
    return 0.0;
}

float Bounds::width() const
{
    return std::abs(m_coords.second.x - m_coords.first.x);
}

float Bounds::height() const
{
    return std::abs(m_coords.second.y - m_coords.first.y);
}

float Bounds::depth() const
{
    return std::abs(m_coords.second.z - m_coords.first.z);
}

Bounds Bounds::rotate_around(const Point& rotation_pt, const Rotation& rotation) const
{
    // When we rotate, the base and end might no longer contain the smallest
    // and largest axis values (on a per-axis basis); recalc here
    auto calc_base = rotation.rotate_coord(rotation_pt, m_coords.first);
    auto calc_end = rotation.rotate_coord(rotation_pt, m_coords.second);
    auto min_x = std::min(calc_base.x, calc_end.x);
    auto max_x = std::max(calc_base.x, calc_end.x);
    auto min_y = std::min(calc_base.y, calc_end.y);
    auto max_y = std::max(calc_base.y, calc_end.y);
    auto min_z = std::min(calc_base.z, calc_end.z);
    auto max_z = std::max(calc_base.z, calc_end.z);
    return {
        Point(min_x, min_y, min_z),
        Point(max_x, max_y, max_z),
    };
}

}
