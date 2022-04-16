// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include "coords.hpp"

namespace viz3 {

std::ostream& operator<<(std::ostream& os, const Point& pt)
{
    os << "{" << pt.x << ", " << pt.y << ", " << pt.z << "}";
    return os;
}

std::ostream& operator<<(std::ostream& os, const std::vector<Point>& pts)
{
    os << "[";
    for (size_t i = 0; i < pts.size(); i++) {
        os << pts[i];
        if (i != pts.size() - 1)
            os << ", ";
    }
    os << "]";
    return os;
}


}
