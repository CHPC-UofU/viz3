// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <tuple>
#include <vector>

#include "box.hpp"
#include "coords.hpp"
#include "geometry.hpp"

namespace viz3 {

void PlaneElement::render(const Path& path, std::shared_ptr<RenderTree> render_tree) const
{
    auto bounds = Bounds();
    for (const auto& path_and_geometry : render_tree->children_of(path))
        bounds += path_and_geometry.second.positioned_bounds();

    auto [descendant_width, _, descendant_depth] = bounds.lengths();

    auto our_padding = padding();
    auto our_width = std::max(width(), descendant_width) + our_padding * 2.0f;
    auto our_depth = std::max(depth(), descendant_depth) + our_padding * 2.0f;
    auto geometry = box_geometry(our_width, height(), our_depth);
    render_tree->update(path, geometry);

    auto offset = Point(our_padding, height(), our_padding);
    render_tree->move_descendants_by(path, offset);
}

}
