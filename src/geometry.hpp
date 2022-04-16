// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <algorithm>
#include <limits>
#include <optional>
#include <tuple>
#include <vector>

#include "bounds.hpp"
#include "color.hpp"
#include "coords.hpp"
#include "rotation.hpp"

namespace viz3 {

using Face = std::tuple<unsigned int, unsigned int, unsigned int>;

struct Geometry {
    explicit Geometry(std::vector<Point> vertexes, std::vector<Face> triangles, Point pos, const color::RGBA& color = color::default_color, float hide_distance = 0.0, float show_distance = std::numeric_limits<float>::infinity(), std::string text = "")
        : m_vertexes(std::move(vertexes))
        , m_triangles(std::move(triangles))
        , m_bounds(compute_bounds())
        , m_pos(pos)
        , m_color(color)
        , m_hide_distance(hide_distance)
        , m_show_distance(show_distance)
        , m_text(text) {};

    static Geometry empty(const Point& pos, const Bounds& bounds, const color::RGBA& color = color::default_color, const std::optional<std::string>& text = std::nullopt)
    {
        auto geometry = Geometry({}, {}, pos, color);
        geometry.m_bounds = bounds;
        if (text)
            geometry.m_text = *text;

        return geometry;
    };
    bool should_draw() const
    {
        return !m_vertexes.empty();
    }

    std::vector<Point> vertexes() const { return m_vertexes; }
    std::vector<Face> triangles() const { return m_triangles; }

    Bounds bounds() const { return m_bounds; }
    Bounds positioned_bounds() const
    {
        auto pos_bounds = bounds();
        return { pos_bounds.base() + m_pos, pos_bounds.end() + m_pos };
    }

    Point pos() const { return m_pos; }
    void set_pos(Point new_pos) { m_pos = new_pos; }
    void offset_pos(Point offset_pos) { m_pos += offset_pos; }

    color::RGBA color() const { return m_color; }
    void set_color(color::RGBA new_color) { m_color = new_color; }

    void rotate_around(const Point&, const Rotation&);

    float hide_distance() const { return m_hide_distance; }
    void set_hide_distance(float new_hide_distance) { m_hide_distance = new_hide_distance; }
    float show_distance() const { return m_show_distance; }
    void set_show_distance(float new_show_distance) { m_show_distance = new_show_distance; }

    void set_text(const std::string& text) { m_text = text; }
    std::string text() const { return m_text; };

    void scale_by(float);
    void stretch_by(unsigned int axis, float);
    Geometry combine_with(const Geometry& other) const;

private:
    Bounds compute_bounds() const;

    std::vector<Point> m_vertexes;
    // FIXME: Rather than storing potentially reused points for each face, perhaps
    //        we should store a sorted array of indicies and then a array of per-face
    //        indicies size
    std::vector<Face> m_triangles;
    Bounds m_bounds;
    Point m_pos;
    color::RGBA m_color;
    float m_hide_distance = 0.0f;
    float m_show_distance = std::numeric_limits<float>::infinity();
    std::string m_text;
};

}
