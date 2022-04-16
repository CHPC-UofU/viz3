// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "geometry.hpp"
#include "path.hpp"
#include "rotation.hpp"

namespace viz3 {

enum class RenderDifferences {
    FirstMissing,
    SecondMissing,
    Pos,
    Bounds,
    Color,
    Text,
};

/*
 * A Tree of geometries, whose hierarchy reflects the Node hiearchy.
 *
 * FIXME: This is really quick and dirty. We have to iterate over all elements
 *        for pretty much everything and it really isn't a tree...
 */
class RenderTree {
public:
    RenderTree()
        : m_insertion_order()
        , m_rendered() {};

    bool needs_updating(const Path&);
    void update(const Path& path, const Geometry&);
    std::optional<Geometry> get(const Path&) const;
    Bounds positioned_bounds_of(const Path& path) const;
    std::vector<std::pair<Path, RenderDifferences>> differences_from(const RenderTree&) const;
    size_t num_children_of(const Path&) const;
    std::vector<std::pair<Path, Geometry>> children_of(const Path&) const;
    std::vector<std::pair<Path, Geometry>> descendants_of(const Path&, bool including) const;
    void move_parent_and_descendants_by(const Path&, const Point&, const Path& excluding);
    void move_parent_and_descendants_by(const Path&, const Point&);
    void move_descendants_by(const Path&, const Point&);
    void scale_parent_and_descendants_by(const Path&, float factor);
    void rotate_parent_and_descendants_in_place(const Path&, const Rotation&);
    void invalidate_parent_and_child_pos(const Path&);

private:
    void move_parent_and_descendants_by_impl(const Path&, const Point&, const Path* excluding, bool excluding_parent);
    void rotate_children_of(const Path&, const Point&, const Rotation&);

    std::vector<Path> m_insertion_order;
    std::map<Path, Geometry> m_rendered;
};

}
