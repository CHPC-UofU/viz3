// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <algorithm>
#include <string>
#include <ostream>
#include <tuple>

#include "value_types.hpp"

namespace viz3::color {

    struct RGBA {
        RGBA(std::tuple<unsigned char, unsigned char, unsigned char> rgb)
            : r(std::get<0>(rgb))
            , g(std::get<1>(rgb))
            , b(std::get<2>(rgb))
            , a(255) {};
        RGBA(std::tuple<unsigned char, unsigned char, unsigned char, float> rgba)
            : r(std::get<0>(rgba))
            , g(std::get<1>(rgba))
            , b(std::get<2>(rgba))
            , a(convert_float_opacity_to_char(std::get<3>(rgba))) {};
        RGBA(unsigned char r, unsigned char g, unsigned char b)
            : r(r)
            , g(g)
            , b(b)
            , a(255) {};
        RGBA(unsigned char r, unsigned char g, unsigned char b, float opacity)
            : r(r)
            , g(g)
            , b(b)
            , a(convert_float_opacity_to_char(opacity)) {};
        explicit RGBA(const std::string& string_color)
            : RGBA(from_string(string_color)) {};
        RGBA(const RGBA&) = default;

        static RGBA from_string(std::string string, float opacity = 1.0);

        static constexpr unsigned char convert_float_opacity_to_char(UnitInterval opacity) {
            return static_cast<unsigned char>(opacity * 255);
        }

        bool operator==(const RGBA& other_color) const
        {
            return r == other_color.r && g == other_color.g && b == other_color.b && a == other_color.a;
        }
        bool operator!=(const RGBA& other_color) const
        {
            return !(*this == other_color);
        }

        // These APIs use floats, rather than UnitInterval, since they are
        // exported to Python, which does not have that type
        float opacity() const
        {
            return static_cast<float>(a) / 255;
        }
        void set_opacity(float opacity)
        {
            a = convert_float_opacity_to_char(UnitInterval(opacity));
        }
        void darken_by(float darkness)
        {
            darkness = 1.0f - UnitInterval(darkness);
            r = static_cast<unsigned char>(static_cast<float>(r) * darkness);
            g = static_cast<unsigned char>(static_cast<float>(g) * darkness);
            b = static_cast<unsigned char>(static_cast<float>(b) * darkness);
        }

        unsigned char r;
        unsigned char g;
        unsigned char b;
        unsigned char a;

        std::string string() const;
        friend std::ostream& operator<<(std::ostream&, const RGBA&);
    };

    static const RGBA black = RGBA { 0, 0, 0, 1.0 };
    static const RGBA white = RGBA { 255, 255, 255, 1.0 };
    static const RGBA default_color = black;
}
