// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <algorithm>
#include <cmath>
#include <numeric>
#include <set>
#include <set>
#include <vector>

#include "bounds.hpp"
#include "coords.hpp"
#include "geometry.hpp"

namespace viz3 {

void Geometry::scale_by(float factor)
{
    m_pos *= factor;

    for (auto& vertex : m_vertexes)
        vertex *= factor;

    m_bounds *= factor;
    m_show_distance *= factor;
    m_hide_distance *= factor;
}

void Geometry::stretch_by(unsigned int axis_index, float amount)
{
    if (m_vertexes.empty())
        return;

    // FIXME? This is kinda weird logic, not sure how to properly do it
    std::set<float> axis_values;
    for (const auto& vertex : m_vertexes)
        axis_values.insert(vertex[axis_index]);

    float axis_values_total = 0.0;
    for (const auto& axis_value : axis_values)
        axis_values_total += axis_value;

    auto avg_value = axis_values_total / axis_values.size();
    for (auto& vertex : m_vertexes)
        if (vertex[axis_index] > avg_value)
            vertex[axis_index] += amount;

    auto offset_pt = Point(0,0,0);
    offset_pt[axis_index] = amount;
    m_bounds = { m_bounds.base(), m_bounds.end() + offset_pt };
}

Geometry Geometry::combine_with(const Geometry& other) const
{
    auto new_pos = (positioned_bounds() + other.positioned_bounds()).base();
    auto offset_pos = m_pos - new_pos;
    auto other_offset_pos = other.m_pos - new_pos;

    size_t vertexes_size = m_vertexes.size();
    std::vector<Point> new_vertexes;
    new_vertexes.reserve(vertexes_size + other.m_vertexes.size());
    for (const auto& vertex : m_vertexes)
        new_vertexes.emplace_back(vertex + offset_pos);
    for (const auto& other_vertex : other.m_vertexes)
        new_vertexes.emplace_back(other_vertex + other_offset_pos);

    auto new_triangles = m_triangles;
    for (const auto& other_triangle : other.m_triangles)
        new_triangles.emplace_back(
            std::get<0>(other_triangle) + vertexes_size,
            std::get<1>(other_triangle) + vertexes_size,
            std::get<2>(other_triangle) + vertexes_size);

    return Geometry(
        new_vertexes,
        new_triangles,
        new_pos,
        m_color,
        m_hide_distance,
        m_show_distance,
        m_text);
}

Bounds Geometry::compute_bounds() const
{
    if (m_vertexes.empty())
        return Bounds();

    auto inf = std::numeric_limits<float>::infinity();
    Point min_pt { inf, inf, inf };
    Point max_pt { -inf, -inf, -inf };
    for (const auto& pt : m_vertexes) {
        if (pt.x < min_pt.x)
            min_pt.x = pt.x;
        if (pt.y < min_pt.y)
            min_pt.y = pt.y;
        if (pt.z < min_pt.z)
            min_pt.z = pt.z;

        if (pt.x > max_pt.x)
            max_pt.x = pt.x;
        if (pt.y > max_pt.y)
            max_pt.y = pt.y;
        if (pt.z > max_pt.z)
            max_pt.z = pt.z;
    }
    return { min_pt, max_pt };
}

void Geometry::rotate_around(const Point& rotation_pt, const Rotation& new_rotation)
{
    m_pos = new_rotation.rotate_coord(rotation_pt, m_pos);
    m_bounds = m_bounds.rotate_around(rotation_pt, new_rotation);

   for (auto& vertex : m_vertexes)
       vertex = new_rotation.rotate_coord(rotation_pt, vertex);
}

}
