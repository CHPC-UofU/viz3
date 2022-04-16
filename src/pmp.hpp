// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include "color.hpp"
#include "element.hpp"
#include "feature.hpp"
#include "render.hpp"

namespace viz3::external {

class SphereElement : public MeshElement<SphereElement, CircularFeature> {
public:
    using MeshElement<SphereElement, CircularFeature>::MeshElement;

    void render(const Path&, std::shared_ptr<RenderTree>) const override;
};

class CylinderElement : public MeshElement<CylinderElement, CircularFeature, SizeFeature> {
public:
    using MeshElement<CylinderElement, CircularFeature, SizeFeature>::MeshElement;

    void render(const Path&, std::shared_ptr<RenderTree>) const override;
};

class ObjElement : public MeshElement<ObjElement, ScaleFeatureSet> {
public:
    ObjElement(std::string name, const AttributeMap& attributes)
        : MeshElement(std::move(name), attributes)
        , m_filepath(attributes.at("path")) {};
    ObjElement(const ObjElement&) = default;

    void render(const Path&, std::shared_ptr<RenderTree>) const override;

private:
    std::string m_filepath;
};

}
