// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <algorithm>
#include <memory>
#include <string>
#include <limits>

#include "color.hpp"
#include "element.hpp"
#include "feature.hpp"

namespace viz3 {

// With the CTRP pattern of BaseElement, we can only have one derived
// Element of that BaseElement (BaseElement must know the second
// derived class so it can create a proper clone() method). We'll introduce
// another template here to allow for multiple derivations of the box element
template <class DerivedBoxElement, class... Features>
class BaseBoxElement : public MeshElement<DerivedBoxElement, SizeFeature, Features...> {
public:
    using MeshElement<DerivedBoxElement, SizeFeature, Features...>::MeshElement;

    void render(const Path& path, std::shared_ptr<RenderTree> render_tree) const override
    {
        auto [width, height, depth] = this->lengths();
        auto geometry = box_geometry(width, height, depth);
        render_tree->update(path, geometry);
    }

    Geometry box_geometry(float width, float height, float depth, Point pos = Point()) const
    {
        std::vector<Point> vertexes = {
            { 0, 0, 0 },
            { 0, height, 0 },
            { width, 0, 0 },
            { width, height, 0 },
            { 0, 0, depth },
            { 0, height, depth },
            { width, 0, depth },
            { width, height, depth },
        };
        /*
         * Note: these are non-trivial hardcoded values. Each value in the triple
         *       indexes into the vertexes, but the order of the points matters.
         *       I couldn't tell you why though... (something with z-positiveness)
         */
        std::vector<Face> triangles = {
            { 1, 2, 0 }, // Bottom
            { 1, 3, 2 },
            { 0, 4, 1 }, // Left Side
            { 4, 5, 1 },
            { 4, 6, 5 }, // Top
            { 6, 7, 5 },
            { 3, 6, 2 }, // Right side
            { 3, 7, 6 },
            { 2, 4, 0 }, // Front
            { 2, 6, 4 },
            { 1, 5, 3 }, // Back
            { 5, 7, 3 }
        };
        return this->construct_geometry(move(vertexes), move(triangles), pos);
    }
};

class BoxElement : public BaseBoxElement<BoxElement> {
public:
    using BaseBoxElement::BaseBoxElement;
};

class PlaneElement : public BaseBoxElement<PlaneElement, PaddingFeature> {
public:
    using BaseBoxElement::BaseBoxElement;

    void render(const Path&, std::shared_ptr<RenderTree>) const override;
};

}
