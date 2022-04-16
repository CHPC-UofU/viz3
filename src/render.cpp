// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <algorithm>
#include <optional>
#include <utility>

#include "coords.hpp"
#include "path.hpp"
#include "render.hpp"

namespace viz3 {

bool RenderTree::needs_updating(const Path& path)
{
    return m_rendered.count(path) == 0;
}

void RenderTree::update(const Path& path, const Geometry& geometry)
{
    if (m_rendered.count(path) == 0)
        m_insertion_order.push_back(path);

    m_rendered.insert_or_assign(path, geometry);
}

std::optional<Geometry> RenderTree::get(const Path& path) const
{
    if (m_rendered.count(path) < 1)
        return {};
    return { m_rendered.at(path) };
}

Bounds RenderTree::positioned_bounds_of(const Path& path) const
{
    // We do this optional weirdness since += with Bounds() as the starter
    // value leaves us with a lower bound of (0,0,0), which might be higher
    // than the real lower bound of all the bounds here.
    auto maybe_bounds = std::optional<Bounds>();
    for (const auto& path_and_child : m_rendered) {
        if (path_and_child.first.is_descendant_of(path, true)) {
            if (maybe_bounds.has_value())
                *maybe_bounds += path_and_child.second.positioned_bounds();
            else
                maybe_bounds = path_and_child.second.positioned_bounds();
        }
    }
    return maybe_bounds.has_value() ? *maybe_bounds : Bounds();
}

std::vector<std::pair<Path, RenderDifferences>> RenderTree::differences_from(const RenderTree& other_render_tree) const
{
    /*
     * Both trees have maps that are sorted by paths, so we can utilize that to
     * get linear time results. We cannot simply use std::set_symmetric_difference
     * from <algorithm> since that only returns a one-item results, which masks
     * the reason for the difference (e.g. did the bounds change, is the geometry
     * missing entirely, etc).
     *
     * Note: m_insertion_order is not needed here since that is the insertion order,
     *       not the order of Path()s with respect to one another like in our map
     */
    std::vector<std::pair<Path, RenderDifferences>> differences {};

    auto first_iter = m_rendered.begin();
    auto first_iter_end = m_rendered.end();
    auto last_iter = other_render_tree.m_rendered.begin();
    auto last_iter_end = other_render_tree.m_rendered.end();

    while (first_iter != first_iter_end && last_iter != last_iter_end) {
        auto first_path = first_iter->first;
        auto first_geometry = first_iter->second;
        auto last_path = last_iter->first;
        auto last_geometry = last_iter->second;

        if (first_path < last_path) {
            // Continue iterating on first; is missing in second
            differences.emplace_back(first_path, RenderDifferences::SecondMissing);
            first_iter++;
            continue;
        }
        if (last_path < first_path) {
            // Continue iterating on last; is missing in first
            differences.emplace_back(last_path, RenderDifferences::FirstMissing);
            last_iter++;
            continue;
        }
        if (first_geometry.pos() != last_geometry.pos())
            differences.emplace_back(first_path, RenderDifferences::Pos);
        if (first_geometry.bounds() != last_geometry.bounds())
            differences.emplace_back(first_path, RenderDifferences::Bounds);
        if (first_geometry.color() != last_geometry.color())
            differences.emplace_back(first_path, RenderDifferences::Color);
        if (first_geometry.text() != last_geometry.text())
            differences.emplace_back(first_path, RenderDifferences::Text);

        first_iter++;
        last_iter++;
    }

    // only one of these paths should be taken
    while (first_iter != first_iter_end) {
        differences.emplace_back(first_iter->first, RenderDifferences::SecondMissing);
        first_iter++;
    }
    while (last_iter != last_iter_end) {
        differences.emplace_back(last_iter->first, RenderDifferences::FirstMissing);
        last_iter++;
    }

    return differences;
}

size_t RenderTree::num_children_of(const Path& path) const
{
    return std::count_if(m_insertion_order.begin(), m_insertion_order.end(), [&](const auto& our_path) {
        return our_path.is_child_of(path);
    });
}

std::vector<std::pair<Path, Geometry>> RenderTree::children_of(const Path& path) const
{
    std::vector<std::pair<Path, Geometry>> children;
    for (const auto& our_path : m_insertion_order)
        if (our_path.is_child_of(path))
            children.emplace_back(our_path, m_rendered.at(our_path));
    return children;
}

std::vector<std::pair<Path, Geometry>> RenderTree::descendants_of(const Path& path, bool including) const
{
    std::vector<std::pair<Path, Geometry>> descendants;
    for (const auto& our_path : m_insertion_order)
        if (our_path.is_descendant_of(path, including))
            descendants.emplace_back(our_path, m_rendered.at(our_path));
    return descendants;
}

void RenderTree::move_parent_and_descendants_by_impl(const Path& path, const Point& by_pos, const Path* excluding_subdescendants_of, bool excluding_parent)
{
    if (!excluding_parent && m_rendered.count(path) > 0) {
        m_rendered.at(path).offset_pos(by_pos);
    }

    // Again, here we don't care about m_insertion_order since addition is commutative
    for (auto& rendered_path_and_geometry : m_rendered) {
        auto& [rendered_path, rendered_geometry] = rendered_path_and_geometry;
        if (rendered_path.is_descendant_of(path)
                && (excluding_subdescendants_of == nullptr
                    || !rendered_path.is_descendant_of(*excluding_subdescendants_of, true))) {
            rendered_geometry.offset_pos(by_pos);
        }
    }
}

void RenderTree::move_parent_and_descendants_by(const Path& path, const Point& by_pos, const Path& excluding)
{
    move_parent_and_descendants_by_impl(path, by_pos, &excluding, false);
}

void RenderTree::move_parent_and_descendants_by(const Path& path, const Point& by_pos)
{
    move_parent_and_descendants_by_impl(path, by_pos, nullptr, false);
}

void RenderTree::move_descendants_by(const Path& path, const Point& by_pos)
{
    move_parent_and_descendants_by_impl(path, by_pos, nullptr, true);
}

void RenderTree::scale_parent_and_descendants_by(const Path& path, float factor)
{
    for (auto& [descendant_path, descendant_geometry] : descendants_of(path, true)) {
        descendant_geometry.scale_by(factor);
        update(descendant_path, descendant_geometry);
    }
}

void RenderTree::rotate_children_of(const Path& path, const Point& rotation_pt, const Rotation& rotation)
{
    auto children_paths_and_geometries = children_of(path);
    for (auto& [child_path, _] : children_paths_and_geometries)
        rotate_children_of(child_path, rotation_pt, rotation);

    auto maybe_geometry = get(path);
    // When rotate_children_of is first called, there may not be a corresponding geometry for that path
    if (maybe_geometry) {
        maybe_geometry->rotate_around(rotation_pt, rotation);
        update(path, *maybe_geometry);
    }
}

void RenderTree::rotate_parent_and_descendants_in_place(const Path& path, const Rotation& rotation)
{
    auto pos_bounds = positioned_bounds_of(path);
    auto old_left_corner_pt = pos_bounds.bottom_left();
    auto rotation_pt = pos_bounds.center();
    rotate_children_of(path, rotation_pt, rotation);

    /*
     * Rotating geometries will move them around our center point; we want these
     * rotations to be in place, so shift them back here. e.g.
     *
     * x -- o
     *
     * -> 90 degrees
     *
     *      x
     *      |
     *      o
     *
     * -> shifted back
     *
     * x
     * |
     * o
     *
     */
    auto new_left_corner_pt = positioned_bounds_of(path).bottom_left();
    auto offset_from_rotation = old_left_corner_pt - new_left_corner_pt;
    move_parent_and_descendants_by(path, offset_from_rotation);
}

void RenderTree::invalidate_parent_and_child_pos(const Path& path)
{
    // FIXME: We shouldn't be doing this, but cache invalidation here is hard
    //        because when we invalidate something we may need to propagate those
    //        changes upwards based on rendering...
    m_rendered.erase(m_rendered.cbegin(), m_rendered.cend());
    m_insertion_order.erase(m_insertion_order.cbegin(), m_insertion_order.cend());

    /*
    // FIXME: Make Render tree an actual tree so we don't have to do a linear scan
    for (auto it = m_rendered.cbegin(); it != m_rendered.cend();)
    {
        const auto& path_and_child = *it;
        if (path_and_child.first.is_descendant_of(path, true))
            it = m_rendered.erase(it);
        else
            ++it;
    }
    */
}

}
