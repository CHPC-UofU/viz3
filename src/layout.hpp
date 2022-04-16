// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <limits>
#include <memory>
#include <optional>
#include <string>

#include "value_types.hpp"
#include "element.hpp"
#include "feature.hpp"
#include "render.hpp"

namespace viz3 {

// Basically just stores sizes, but does not layout children
class NoLayoutElement : public BaseElement<NoLayoutElement, SizeFeature> {
public:
    using BaseElement::BaseElement;

    void render(const Path&, std::shared_ptr<RenderTree>) const override {};
};

class GridElement : public BaseElement<GridElement, SpacingFeature> {
public:
    using BaseElement::BaseElement;

    void render(const Path&, std::shared_ptr<RenderTree>) const override;
};

class ScaleElement : public BaseElement<ScaleElement, ScaleFeatureSet> {
public:
    using BaseElement::BaseElement;

    void render(const Path&, std::shared_ptr<RenderTree>) const override;
};

class HideShowElement : public BaseElement<HideShowElement, HideShowFeature> {
public:
    using BaseElement::BaseElement;

    void render(const Path&, std::shared_ptr<RenderTree>) const override;
};

class RotateElement : public BaseElement<RotateElement, RotateFeature> {
public:
    using BaseElement::BaseElement;

    void render(const Path&, std::shared_ptr<RenderTree>) const override;
};

class JuxtaposeElement : public BaseElement<JuxtaposeElement, JuxtaposeFeatureSet> {
public:
    using BaseElement::BaseElement;

    void render(const Path&, std::shared_ptr<RenderTree>) const override;
};

class PaddingElement : public BaseElement<PaddingElement, PaddingFeature, SizeFeature> {
public:
    using BaseElement::BaseElement;

    void render(const Path&, std::shared_ptr<RenderTree>) const override;
};

class StreetElement : public BaseElement<StreetElement, SpacingFeature, AxisFeature> {
public:
    using BaseElement::BaseElement;

    void render(const Path&, std::shared_ptr<RenderTree>) const override;

private:
    void stretch_street(const Path&, Geometry, const Bounds&, const std::shared_ptr<RenderTree>&) const;
    void street_layout_pts_from_geometry(const Geometry&, const std::vector<Geometry>&, Point&, std::vector<Point>&) const;
    std::vector<Point> scale_into_axis_aligned_blocks(const std::vector<std::pair<int,int>>&, const std::vector<Point>&) const;
};

}
