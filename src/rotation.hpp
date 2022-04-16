// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <boost/qvm/all.hpp>

#include "coords.hpp"

namespace qvm = boost::qvm;

namespace viz3 {

/*
 * Stores a Tait_Bryan rotation in a 3D space.
 *
 * Does not handle gimbal lock.
 */
struct Rotation {
    // Tait-Bryan angles; except internally we swapped the notion of y and z in
    // viz3 for dumb ignorant reasons. So the conventional zxy form is actually yxz.
    // See https://en.wikipedia.org/wiki/Euler_angles#Tait–Bryan_angles
    Rotation(float yaw_degrees, float pitch_degrees, float roll_degrees)
        : m_rotation_matrix(qvm::rot_mat_yxz<3>(degrees_to_radians(yaw_degrees), degrees_to_radians(pitch_degrees), degrees_to_radians(roll_degrees)))
    {
    }
    Rotation(float degrees = 0.0f) // the non-3d simple notion of rotation
        : Rotation(degrees, 0.0f, 0.0f) {};
    static Rotation none() { return {}; }

    bool operator==(const Rotation& other_rotation) const
    {
        return m_rotation_matrix == other_rotation.m_rotation_matrix;
    }
    bool operator!=(const Rotation& other_rotation) const
    {
        return !(*this == other_rotation);
    }
    Rotation operator*(const Rotation& other_rotation) const
    {
        auto rotation = Rotation();
        rotation.m_rotation_matrix = m_rotation_matrix * other_rotation.m_rotation_matrix;
        return rotation;
    }
    void operator*=(const Rotation& other_rotation)
    {
        m_rotation_matrix *= other_rotation.m_rotation_matrix;
    }

    Point rotate_coord(const Point&, const Point& pt) const;
    Point rotate_coord(const Point& pt) const;
    float rotation() const;
    float yaw() const;
    float pitch() const;
    float roll() const;

    static constexpr float degrees_to_radians(float degrees)
    {
        return (degrees * 3.1415f) / 180;
    }
    static constexpr float radians_to_degrees(float radians)
    {
        return (180 / 3.1415f) * radians;
    }

    std::string string() const;
    friend std::ostream& operator<<(std::ostream&, const Rotation&);

private:
    // One cannot simply store angles, add them we we add rotations together,
    // and expect the end rotation to work out; it turns out 3D rotations are
    // messy. So use boost::qvm to do the dirty correct work. A matrix here
    // allows for us to easily add rotations together and apply those rotations
    // to coords.
    //
    // Note: we can also use Point() with boost::qvm since we implemented the
    //       qvm's vec traits for Point().
    qvm::mat<float, 3, 3> m_rotation_matrix;
};

}
