// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <cmath>

#include "coords.hpp"
#include "rotation.hpp"

namespace viz3 {

Point Rotation::rotate_coord(const Point& around_pt, const Point& pt) const
{
    auto translated_pt = pt - around_pt;
    auto rotated_translated_pt = m_rotation_matrix * translated_pt;
    return around_pt + rotated_translated_pt;
}

Point Rotation::rotate_coord(const Point& pt) const
{
    return rotate_coord(Point(), pt);  // rotate around origin
}

float Rotation::rotation() const {
    return yaw();
}

// For these, see https://en.wikipedia.org/wiki/Euler_angles#Conversion_to_other_orientation_representations
// We are using tait-bryan yxz representation (because our y is swapped with z
// from the convention) and indexes are 0-based unlike in Wikipedia
float Rotation::yaw() const
{
    return radians_to_degrees(atanf(qvm::A02(m_rotation_matrix) / qvm::A22(m_rotation_matrix)));
}

float Rotation::pitch() const
{
    auto r12 = qvm::A12(m_rotation_matrix);
    return radians_to_degrees(atanf(-r12 / sqrtf(1 - (r12 * r12))));
}

float Rotation::roll() const
{
    return radians_to_degrees(atanf(qvm::A10(m_rotation_matrix) / qvm::A11(m_rotation_matrix)));
}

std::string Rotation::string() const
{
    std::stringstream stream {};
    stream << *this;
    return stream.str();
}

std::ostream& operator<<(std::ostream& os, const Rotation& rotation)
{
    os << "Rotation(";
    os << "yaw: " << rotation.yaw() << ", ";
    os << "pitch: " << rotation.pitch() << ", ";
    os << "roll: " << rotation.roll();
    os << ")";
    return os;
}

}
