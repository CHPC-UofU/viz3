// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <string>
#include <algorithm>

enum class Axis : int {
    X = 0,
    Y,
    Z,
};

std::ostream& operator<<(std::ostream&, const Axis&);

const char* axis_string(Axis);
Axis string_to_axis(const std::string_view&);
Axis opposite_axis(Axis);

enum class Alignment {
    Left,
    Center,
    Right,
};

std::ostream& operator<<(std::ostream&, const Alignment&);

const char* alignment_string(Alignment);
Alignment string_to_alignment(const std::string_view&);

// Wrapper floating-point class that clamps values between 0-1.
class UnitInterval {
public:
    constexpr UnitInterval() = default;
    constexpr UnitInterval(float value)
        : m_value(std::clamp(value, 0.0f, 1.0f)) {};

    // Conversion operator
    constexpr operator float() { return m_value; }
    constexpr operator float() const { return m_value; }

private:
    float m_value = 0.0f;
};
