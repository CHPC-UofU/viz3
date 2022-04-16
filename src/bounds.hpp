// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once

#include <ostream>
#include <tuple>

#include "coords.hpp"
#include "rotation.hpp"

namespace viz3 {

struct Bounds {
    Bounds()
        : m_coords() {};
    Bounds(std::pair<Point, Point> base_and_end_coord)
        : m_coords(std::get<0>(base_and_end_coord), std::get<1>(base_and_end_coord)) {};
    Bounds(Point base_coord, Point end_coord)
        : m_coords(base_coord, end_coord) {};
    Bounds(float width, float height, float depth)
        : m_coords(Point(), Point(width, height, depth)) {};

    Point base() const
    {
        return m_coords.first;
    }
    Point end() const
    {
        return m_coords.second;
    }
    Point center() const
    {
        auto [width, height, depth] = lengths();
        return m_coords.first + Point(width / 2, height / 2, depth / 2);
    };
    Point bottom_left() const
    {
        return m_coords.first;
    };
    Point bottom_right() const
    {
        return m_coords.first + Point(m_coords.second.x, 0.0, 0.0);
    };
    Bounds strip_pos();

    bool operator==(const Bounds& other_bounds) const
    {
        return m_coords.first == other_bounds.m_coords.first && m_coords.second == other_bounds.m_coords.second;
    }
    bool operator!=(const Bounds& other_bounds) const
    {
        return !(*this == other_bounds);
    }

    Bounds operator+(const Bounds& other_bounds) const
    {
        auto new_bounds = *this;
        new_bounds += other_bounds;
        return new_bounds;
    }
    Bounds& operator+=(const Bounds& other_bounds)
    {
        // If (0,0,0) - (0,0,0) we don't have any bounds; so adopt other bounds
        if (base() == Point() && end() == Point()) {
            m_coords = other_bounds.m_coords;
            return *this;
        }

        auto [base_x, base_y, base_z] = base();
        auto [base_other_x, base_other_y, base_other_z] = other_bounds.base();
        auto base_coord = Point(
            base_x > base_other_x ? base_other_x : base_x,
            base_y > base_other_y ? base_other_y : base_y,
            base_z > base_other_z ? base_other_z : base_z);
        auto [end_x, end_y, end_z] = end();
        auto [end_other_x, end_other_y, end_other_z] = other_bounds.end();
        auto end_coord = Point(
            end_x > end_other_x ? end_x : end_other_x,
            end_y > end_other_y ? end_y : end_other_y,
            end_z > end_other_z ? end_z : end_other_z);
        m_coords = { base_coord, end_coord };
        return *this;
    }

    Bounds operator-(const Point& offset_pt) const
    {
        auto new_bounds = *this;
        new_bounds -= offset_pt;
        return new_bounds;
    }
    Bounds& operator-=(const Point& offset_pt)
    {
        m_coords.first -= offset_pt;
        m_coords.second -= offset_pt;
        return *this;
    }
    Bounds operator+(const Point& offset_pt) const
    {
        auto new_bounds = *this;
        new_bounds += offset_pt;
        return new_bounds;
    }
    Bounds& operator+=(const Point& offset_pt)
    {
        m_coords.first += offset_pt;
        m_coords.second += offset_pt;
        return *this;
    }

    Bounds operator*(float factor) const
    {
        return { m_coords.first * factor, m_coords.second * factor };
    }
    Bounds& operator*=(float factor)
    {
        m_coords.first *= factor;
        m_coords.second *= factor;
        return *this;
    }

    std::tuple<float, float, float> lengths() const;
    float axis_length(Axis axis) const;

    Bounds rotate_around(const Point& rotation_pt, const Rotation& rotation) const;

    float width() const;
    float height() const;
    float depth() const;

    bool is_nan() const
    {
        return m_coords.first.is_nan() || m_coords.second.is_nan();
    }
    bool is_finite() const
    {
        return m_coords.first.is_finite() && m_coords.second.is_finite();
    }

    friend std::ostream& operator<<(std::ostream&, const Bounds&);
    std::string string() const
    {
        std::stringstream str {};
        str << *this;
        return str.str();
    }

private:
    std::pair<Point, Point> m_coords;
};

}
