// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <algorithm>
#include <cassert>
#include <cmath>
#include <limits>
#include <numeric>
#include <vector>

#include "coords.hpp"
#include "layout.hpp"
#include "render.hpp"

namespace viz3 {

using XZIntPt = std::pair<int, int>;
using XZLengths = std::pair<std::vector<float>, std::vector<float>>;

static std::vector<XZIntPt> generate_seq_grid_points(unsigned int diameter)
{
    std::vector<XZIntPt> pts;
    pts.reserve(diameter * diameter);

    for (unsigned int row = 0; row < diameter; row++)
        for (unsigned int col = 0; col < diameter; col++)
            pts.emplace_back(row, col);

    return pts;
}

static std::pair<std::vector<float>, std::vector<float>> compute_non_uniform_grid_xz_lengths(const std::vector<std::pair<Path, Geometry>>& child_path_geometry_map, const std::vector<XZIntPt>& pts)
{
    std::vector<float> x_lengths(child_path_geometry_map.size(), 0.0);
    std::vector<float> z_lengths(child_path_geometry_map.size(), 0.0);

    auto pt_it = pts.begin();
    for (const auto& child_path_and_geometry : child_path_geometry_map) {
        auto pt = *pt_it++;
        auto child_width_height_depth = child_path_and_geometry.second.bounds().lengths();

        auto x = std::get<0>(pt);
        auto z = std::get<1>(pt);
        x_lengths[x] = std::max(x_lengths[x], std::get<0>(child_width_height_depth));
        z_lengths[z] = std::max(z_lengths[z], std::get<2>(child_width_height_depth));
    }

    return { x_lengths, z_lengths };
}

void GridElement::render(const Path& path, std::shared_ptr<RenderTree> render_tree) const
{
    auto child_path_geometry_map = render_tree->children_of(path);

    unsigned int diameter = std::ceil(std::sqrt(child_path_geometry_map.size()));
    auto grid_pts = generate_seq_grid_points(diameter);
    auto [x_lengths, z_lengths] = compute_non_uniform_grid_xz_lengths(child_path_geometry_map, grid_pts);

    auto grid_pt_it = grid_pts.begin();
    for (const auto& child_path_and_geometry : child_path_geometry_map) {
        auto pt = *grid_pt_it++;

        auto plus_spacing_func = [&](auto prev, auto curr) {
            return prev + curr + spacing();
        };

        auto pt_x = std::get<0>(pt);
        auto pt_z = std::get<1>(pt);
        float x = std::accumulate(x_lengths.begin(), std::next(x_lengths.begin(), pt_x), 0.0f, plus_spacing_func);
        float z = std::accumulate(z_lengths.begin(), std::next(z_lengths.begin(), pt_z), 0.0f, plus_spacing_func);

        auto by_pos = Point(x, 0.0, z);
        render_tree->move_parent_and_descendants_by(child_path_and_geometry.first, by_pos);
    }
}

void ScaleElement::render(const Path& path, std::shared_ptr<RenderTree> render_tree) const
{
    auto [width, height, depth] = render_tree->positioned_bounds_of(path).lengths();
    auto factor = compute_scale_factor(width, height, depth);
    render_tree->scale_parent_and_descendants_by(path, factor);
}

void HideShowElement::render(const Path& path, std::shared_ptr<RenderTree> render_tree) const
{
    auto [hide_distance, show_distance] = hide_and_show_distances();

    auto descendant_path_and_geometries = render_tree->descendants_of(path, false);
    for (auto& [descendant_path, descendant_geometry] : descendant_path_and_geometries) {
        if (clamp_descendant_hide_distances() && descendant_geometry.hide_distance() < hide_distance)
            descendant_geometry.set_hide_distance(hide_distance);
        if (clamp_descendant_show_distances() && descendant_geometry.show_distance() < show_distance)
            descendant_geometry.set_show_distance(show_distance);

        render_tree->update(descendant_path, descendant_geometry);
    }
}

void RotateElement::render(const Path& path, std::shared_ptr<RenderTree> render_tree) const
{
    render_tree->rotate_parent_and_descendants_in_place(path, rotation());
}

void JuxtaposeElement::render(const Path& path, std::shared_ptr<RenderTree> render_tree) const
{
    auto our_children = render_tree->children_of(path);
    if (our_children.empty())
        return;

    std::vector<Path> our_paths {};
    our_paths.reserve(our_children.size());
    for (const auto& [child_path, _] : our_children)
        our_paths.emplace_back(child_path);

    juxtapose(our_paths, render_tree);

    auto our_axis = axis();
    if (!axis_length_is_defaulted(our_axis))
        center_within_axis_length(our_paths, render_tree, our_axis);

    auto pos_bounds = positioned_bounds_with_provided_lengths(our_paths, render_tree);
    if (!axis_is_defaulted())
        align(our_paths, render_tree, pos_bounds, our_axis, alignment());

    auto geometry = Geometry::empty(pos_bounds.base(), pos_bounds.strip_pos());
    render_tree->update(path, geometry);
}

void PaddingElement::render(const Path& path, std::shared_ptr<RenderTree> render_tree) const
{
    auto child_bounds = render_tree->positioned_bounds_of(path);
    auto [children_width, children_height, children_depth] = child_bounds.lengths();
    auto [width, height, depth] = lengths();
    if (width_is_defaulted())
        width = children_width;
    if (height_is_defaulted())
        height = children_height;
    if (depth_is_defaulted())
        depth = children_depth;

    Bounds bounds { Point(), Point(width, height, depth) };
    auto geometry = Geometry::empty(child_bounds.base(), bounds);
    render_tree->update(path, geometry);
}

static std::map<int, std::vector<float>> compute_per_axis_block_sizes(const std::vector<Point>& sizes, const std::vector<XZIntPt>& pts, Axis axis)
{
    assert(sizes.size() == pts.size());
    assert(axis == Axis::X || axis == Axis::Z);

    std::map<int, std::vector<std::pair<XZIntPt, int>>> per_axis_value_pts_and_indexes;
    for (size_t i = 0; i < pts.size(); i++) {
        const auto& pt = pts[i];
        auto axis_value = axis == Axis::X ? pt.first : pt.second;
        per_axis_value_pts_and_indexes[axis_value].emplace_back(pt, i);
    }

    for (auto& [axis_value, indexes] : per_axis_value_pts_and_indexes) {
        std::sort(indexes.begin(), indexes.end(), [](const auto& first_pt_and_index, const auto& second_pt_and_index) {
            return first_pt_and_index.first < second_pt_and_index.first;
        });
    }

    std::map<int, std::vector<float>> per_axis_value_sizes;
    for (const auto& [axis_value, pts_and_indexes] : per_axis_value_pts_and_indexes) {
        for (const auto& [_, index] : pts_and_indexes) {
            auto& [width, _1, depth] = sizes[index];
            per_axis_value_sizes[axis_value].push_back(axis == Axis::X ? width : depth);
        }
    }

    return per_axis_value_sizes;
}

static XZLengths compute_plane_grid_block_sizes(const std::vector<Point>& sizes, int nrows, int ncols,
                                                const std::vector<XZIntPt>& pts)
{
    std::vector<float> width_per_row(nrows, 0.0f);
    std::vector<float> depth_per_col(ncols, 0.0f);

    assert(pts.size() == sizes.size());
    for (size_t i = 0; i < pts.size(); i++) {
        const auto& [row, col] = pts[i];
        const auto& [width, _, depth] = sizes[i];
        width_per_row[row] = std::max(width_per_row[row], width);
        depth_per_col[col] = std::max(depth_per_col[col], depth);
    }

    return { width_per_row, depth_per_col };
}

std::vector<Point> StreetElement::scale_into_axis_aligned_blocks(const std::vector<XZIntPt>& pts, const std::vector<Point>& sizes) const
{
    if (pts.empty())
        return {};

    int nrows = static_cast<int>(std::max_element(pts.begin(), pts.end(), [](const auto& first_pt, const auto& second_pt) {
        return first_pt.first < second_pt.first;
    })->first) + 1;
    int ncols = static_cast<int>(std::max_element(pts.begin(), pts.end(), [](const auto& first_pt, const auto& second_pt) {
        return first_pt.second < second_pt.second;
    })->second) + 1;

    assert(axis() == Axis::X || axis() == Axis::Z);

    // e.g. normal perfectly aligned block sizes, returned as per-col sizes and per-row sizes
    auto [row_lengths, col_lengths] = compute_plane_grid_block_sizes(sizes, nrows, ncols, pts);
    Axis opposite_axis = axis() == Axis::Z ? Axis::X : Axis::Z;
    auto per_axis_value_lengths = compute_per_axis_block_sizes(sizes, pts, opposite_axis);

    std::vector<Point> new_pts;
    for (const auto& pt : pts) {
        auto [row, col] = pt;

        float col_block_offset = 0.0f, row_block_offset = 0.0f;
        if (axis() == Axis::X) {
            assert(col >= 0 && col_lengths.size() > static_cast<size_t>(col));
            assert(row >= 0 && per_axis_value_lengths[col].size() > static_cast<size_t>(row));
            col_block_offset = std::accumulate(col_lengths.begin(), col_lengths.begin() + col, 0.0f);
            row_block_offset = std::accumulate(per_axis_value_lengths[col].begin(), per_axis_value_lengths[col].begin() + row, 0.0f);
            row_block_offset += spacing() * static_cast<float>(row);
        }
        else {
            assert(axis() == Axis::Z);
            assert(row >= 0 && row_lengths.size() > static_cast<size_t>(row));
            assert(col >= 0 && per_axis_value_lengths[row].size() > static_cast<size_t>(col));
            row_block_offset = std::accumulate(row_lengths.begin(), row_lengths.begin() + row, 0.0f);
            col_block_offset = std::accumulate(per_axis_value_lengths[row].begin(), per_axis_value_lengths[row].begin() + col, 0.0f);
            col_block_offset += spacing() * static_cast<float>(col);
        }

        new_pts.emplace_back(row_block_offset, 0.0f, col_block_offset);
    }

    return new_pts;
}


void StreetElement::street_layout_pts_from_geometry(const Geometry& street_geometry,
                                                    const std::vector<Geometry>& house_geometries,
                                                    Point& out_street_pt, std::vector<Point>& out_house_pts) const
{
    // FIXME: This abomination and corresponding functions is because the code
    //        was directly copied from Python code that was also poorly written
    assert(house_geometries.size() >= 1);

    auto street_pt =  axis() == Axis::X ? std::make_pair(0, 1) : std::make_pair(1, 0);
    std::vector<XZIntPt> all_street_pts { street_pt };

    for (int i = 0; i < ceil(static_cast<double>(house_geometries.size()) / 2.0); i++) {
        for (int j = 0; j <= 2; j += 2) {
            switch (axis()) {
            case Axis::X:
                all_street_pts.emplace_back(i, j);
                continue;
            case Axis::Z:
                all_street_pts.emplace_back(j, i);
                continue;
            }
            assert(false);
        }
    }

    // Truncate possible extra pt
    auto street_pts = std::vector<XZIntPt>(all_street_pts.begin(), all_street_pts.begin() + static_cast<long>(house_geometries.size()) + 1);

    std::vector<Point> sizes { street_geometry.bounds().lengths() };
    for (const auto& house_geometry : house_geometries)
        sizes.emplace_back(house_geometry.bounds().lengths());

    auto new_pts = scale_into_axis_aligned_blocks(street_pts, sizes);
    out_street_pt = new_pts[0];
    assert(new_pts.size() > 1);
    out_house_pts = std::vector<Point>(new_pts.begin() + 1, new_pts.end());
}

void StreetElement::stretch_street(const Path& street_path, Geometry street_geometry, const Bounds& house_bounds, const std::shared_ptr<RenderTree>& render_tree) const
{
    assert(axis() == Axis::X || axis() == Axis::Z);

    auto street_bounds = street_geometry.bounds();
    auto curr_street_length = axis() == Axis::X ? street_bounds.width() : street_bounds.depth();
    auto wanted_street_length = axis() == Axis::X ? house_bounds.width() : house_bounds.depth();
    wanted_street_length += spacing();

    auto stretch_amount = std::max(wanted_street_length - curr_street_length, 0.0f);

    // FIXME: Make axis implicitly convertable to int
    street_geometry.stretch_by(static_cast<unsigned int>(axis()), stretch_amount);
    render_tree->update(street_path, street_geometry);
}

void StreetElement::render(const Path& path, std::shared_ptr<RenderTree> render_tree) const
{
    auto our_children = render_tree->children_of(path);
    if (our_children.size() <= 1)  // Need both house and street!
        return;

    assert(axis() == Axis::X || axis() == Axis::Z);
    auto& [street_path, street_geometry] = *(our_children.end() - 1);
    std::vector<Path> house_paths;
    std::vector<Geometry> house_geometries;
    for (auto house_it = our_children.begin(); house_it != our_children.end() - 1; house_it++) {
        auto& [house_path, house_geometry] = *house_it;
        house_paths.emplace_back(house_path);
        house_geometries.emplace_back(house_geometry);
    }

    Point street_pt;
    std::vector<Point> house_pts;
    street_layout_pts_from_geometry(street_geometry, house_geometries, street_pt, house_pts);
    assert(house_pts.size() == house_paths.size());
    auto min_x = std::min_element(house_pts.begin(), house_pts.end(), [](const auto& first_pt, const auto& second_pt) {
        return first_pt.x < second_pt.x;
    })->x;
    auto min_z = std::min_element(house_pts.begin(), house_pts.end(), [](const auto& first_pt, const auto& second_pt) {
        return first_pt.z < second_pt.z;
    })->z;

    Bounds house_bounds;
    assert(house_paths.size() == house_pts.size());
    for (int i = 0; i < static_cast<int>(house_paths.size()); i++) {
        const auto& child_path = house_paths[i];
        const auto& house_pt = house_pts[i];
        render_tree->move_parent_and_descendants_by(child_path, house_pt);

        bool is_on_right_side = (axis() == Axis::Z) ? house_pt.x > min_x : house_pt.z > min_z;
        if (is_on_right_side)
            render_tree->rotate_parent_and_descendants_in_place(child_path, Rotation(180));

        house_bounds += render_tree->positioned_bounds_of(child_path);
    }

    stretch_street(street_path, street_geometry, house_bounds, render_tree);

    render_tree->move_parent_and_descendants_by(street_path, street_pt);
}

}
