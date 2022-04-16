// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <boost/qvm/all.hpp>
#include <cassert>
#include <cmath>
#include <ostream>
#include <sstream>
#include <string>
#include <tuple>
#include <utility>
#include <vector>
#include "value_types.hpp"

namespace viz3 {

struct Point {
    constexpr Point()
        : x(0.0f)
        , y(0.0f)
        , z(0.0f) {};
    constexpr Point(float x, float y, float z)
        : x(x)
        , y(y)
        , z(z) {};
    constexpr Point(std::tuple<float, float, float> xyz)
        : x(std::get<0>(xyz))
        , y(std::get<1>(xyz))
        , z(std::get<2>(xyz)) {};

    float x;
    float y;
    float z;

    constexpr Point operator+(const Point& pt) const
    {
        return { x + pt.x, y + pt.y, z + pt.z };
    }
    constexpr Point& operator+=(const Point& pt)
    {
        x += pt.x;
        y += pt.y;
        z += pt.z;
        return *this;
    }
    constexpr Point operator-(const Point& pt) const
    {
        return { x - pt.x, y - pt.y, z - pt.z };
    }
    constexpr Point& operator-=(const Point& pt)
    {
        x -= pt.x;
        y -= pt.y;
        z -= pt.z;
        return *this;
    }
    constexpr Point operator*=(float factor)
    {
        x *= factor;
        y *= factor;
        z *= factor;
        return *this;
    }
    constexpr Point operator*(float factor) const
    {
        return { x * factor, y * factor, z * factor };
    }
    constexpr bool operator==(const Point& pt) const
    {
        return x == pt.x && y == pt.y && z == pt.z;
    }
    constexpr bool operator!=(const Point& pt) const
    {
        return !(*this == pt);
    }
    constexpr bool operator<(const Point& pt) const
    {
        return x < pt.x || y < pt.y || z < pt.z;
    }
    constexpr bool operator>(const Point& pt) const
    {
        return x > pt.x && y > pt.y && z > pt.z;
    }

    // These are dumb and only to help boost issues; replace with Axis?
    constexpr float operator[](unsigned char index) const
    {
        switch(index) {
        case 0:
            return x;
        case 1:
            return y;
        case 2:
            return z;
        default:
            assert(false);  // panic?
            return z;
        };
    }
    constexpr float& operator[](unsigned char index)
    {
        switch(index) {
        case 0:
            return x;
        case 1:
            return y;
        case 2:
            return z;
        default:
            assert(false);  // panic?
            return z;
        };
    }
    constexpr float& operator[](Axis axis)
    {
        switch(axis) {
        case Axis::X:
            return x;
        case Axis::Y:
            return y;
        case Axis::Z:
            return z;
        default:;
        };

        assert(false);
        return z;
    }

    bool is_nan() const
    {
        return std::isnan(x) || std::isnan(y) || std::isnan(z);
    }
    bool is_finite() const
    {
        return std::isfinite(x) && std::isfinite(y) && std::isfinite(z);
    }

    friend std::ostream& operator<<(std::ostream&, const Point&);
    friend std::ostream& operator<<(std::ostream&, const std::vector<Point>&);
    std::string string() const
    {
        std::stringstream str {};
        str << *this;
        return str.str();
    }
};

}

namespace std {

template <>
struct hash<viz3::Point> {
    std::size_t operator()(const viz3::Point& pt) const
    {
        using std::hash;
        using std::size_t;
        using std::string;

        // Compute individual hash values for first,
        // second and third and combine them using XOR
        // and bit shifting:
        return ((hash<float>()(pt.x) ^ (hash<float>()(pt.y) << 1)) >> 1) ^ (hash<float>()(pt.z) << 1);
    }
};

}

template <>
struct boost::qvm::vec_traits<viz3::Point>: vec_traits_defaults<viz3::Point,float,3>
{
    template <int I>
    static inline scalar_type & write_element(viz3::Point& pt) {
        return pt[I];
    }

    template <int I>
    static inline scalar_type read_element(viz3::Point const & pt) {
        return pt[I];
    }
};
