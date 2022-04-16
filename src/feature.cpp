// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <string>

#include <boost/graph/adjacency_list.hpp>
#include <boost/graph/topological_sort.hpp>

#include "feature.hpp"

namespace viz3 {

void TextFeature::update_from_attributes(const AttributeMap& attributes)
{
    auto iter = attributes.find("text");
    if (iter != attributes.end())
        set_text(iter->second);
}

AttributeMap TextFeature::attributes() const
{
    auto attributes = AttributeMap();
    attributes.try_emplace("text", m_text.string());
    return attributes;
}

void TextFeature::compute_and_update_ancestor_values(AncestorValues& ancestor_values)
{
    m_text.update_ancestor_values(ancestor_values);
}

void SizeFeature::update_from_attributes(const AttributeMap& attributes)
{
    for (const auto& [attribute_name, attribute_value] : attributes) {
        if (m_width.matches_attribute_name(attribute_name))
            m_width.update_from_attribute_value(attribute_value);
        else if (m_height.matches_attribute_name(attribute_name))
            m_height.update_from_attribute_value(attribute_value);
        else if (m_depth.matches_attribute_name(attribute_name))
            m_depth.update_from_attribute_value(attribute_value);
    }
}

AttributeMap SizeFeature::attributes() const
{
    auto attributes = AttributeMap();
    attributes.try_emplace("width", m_width.string());
    attributes.try_emplace("height", m_height.string());
    attributes.try_emplace("depth", m_depth.string());
    return attributes;
}

void SizeFeature::compute_and_update_ancestor_values(AncestorValues& ancestor_values)
{
    std::map<std::string, AbstractValue&> values {{
        {m_width.name(), m_width},
        {m_height.name(), m_height},
        {m_depth.name(), m_depth},
    }};
    std::map<std::string, std::optional<std::string>> dependencies {{
        {m_width.name(), m_width.is_relative() ? std::make_optional(m_width.relative_name()) : std::nullopt },
        {m_height.name(), m_height.is_relative() ? std::make_optional(m_height.relative_name()) : std::nullopt },
        {m_depth.name(), m_depth.is_relative() ? std::make_optional(m_depth.relative_name()) : std::nullopt },
    }};
    std::map<std::string, std::string> aliases {{
        {m_width.abbreviation(), m_width.name()},
        {m_height.abbreviation(), m_height.name()},
        {m_depth.abbreviation(), m_depth.name()},
    }};
    auto ordered_names = topological_sort_with_aliases(dependencies, aliases);
    assert(ordered_names.size() == dependencies.size());

    for (const auto& name : ordered_names)
        values.at(name).update_ancestor_values(ancestor_values);
}

void ColorFeature::update_from_attributes(const AttributeMap& attributes)
{
    auto iter = attributes.find("color");
    if (iter != attributes.end())
        m_color.set_value(color::RGBA::from_string(iter->second));

    iter = attributes.find("darkness");
    if (iter != attributes.end())
        m_darkness.set_value(std::stof(iter->second));
}

AttributeMap ColorFeature::attributes() const
{
    auto attributes = AttributeMap();
    attributes.try_emplace("color", m_color.string());
    attributes.try_emplace("darkness", m_darkness.string());
    return attributes;
}

void ColorFeature::compute_and_update_ancestor_values(AncestorValues& ancestor_values)
{
    m_color.update_ancestor_values(ancestor_values);
}

color::RGBA ColorFeature::compute_color(float opacity) const
{
    auto raw_color = color();
    raw_color.set_opacity(opacity);
    raw_color.darken_by(darkness());
    return raw_color;
}

void OpticsFeature::update_from_attributes(const AttributeMap& attributes)
{
    auto iter = attributes.find("opacity");
    if (iter != attributes.end())
        m_opacity.set_value(std::stof(iter->second));
}

AttributeMap OpticsFeature::attributes() const
{
    auto attributes = AttributeMap();
    attributes.try_emplace("opacity", m_opacity.string());
    return attributes;
}

void OpticsFeature::compute_and_update_ancestor_values(AncestorValues& ancestor_values)
{
    m_opacity.update_ancestor_values(ancestor_values);
}

void HideShowFeature::update_from_attributes(const AttributeMap& attributes)
{
    auto iter = attributes.find("hide_distance");
    if (iter != attributes.end())
        m_hide_distance.set_value(std::stof(iter->second));

    iter = attributes.find("show_distance");
    if (iter != attributes.end())
        m_show_distance.set_value(std::stof(iter->second));

    iter = attributes.find("clamp_descendant_show_distances");
    if (iter != attributes.end())
        m_clamp_descendant_show_distances.set_value(iter->second == "true");

    iter = attributes.find("clamp_descendant_hide_distances");
    if (iter != attributes.end())
        m_clamp_descendant_hide_distances.set_value(iter->second == "true");
}

AttributeMap HideShowFeature::attributes() const
{
    auto attributes = AttributeMap();
    attributes.try_emplace("hide_distance", m_hide_distance.string());
    attributes.try_emplace("show_distance", m_show_distance.string());
    return attributes;
}

void HideShowFeature::compute_and_update_ancestor_values(AncestorValues& ancestor_values)
{
    m_hide_distance.update_ancestor_values(ancestor_values);
    m_show_distance.update_ancestor_values(ancestor_values);
}

void RotateFeature::update_from_attributes(const AttributeMap& attributes)
{
    auto iter = attributes.find("angle");
    if (iter == attributes.end())
        iter = attributes.find("degrees");

    if (iter != attributes.end()) {
        m_rotation.set_value(Rotation(std::stof(iter->second)));
        return;
    }

    float yaw = m_rotation.value().yaw();
    float pitch = m_rotation.value().pitch();
    float roll = m_rotation.value().roll();
    iter = attributes.find("yaw");
    if (iter != attributes.end())
        yaw = std::stof(iter->second);

    iter = attributes.find("pitch");
    if (iter != attributes.end())
        pitch = std::stof(iter->second);

    iter = attributes.find("roll");
    if (iter != attributes.end())
        roll = std::stof(iter->second);

    m_rotation.set_value(Rotation(yaw, pitch, roll));
}

AttributeMap RotateFeature::attributes() const
{
    auto attributes = AttributeMap();
    assert(!m_rotation.is_relative());

    auto rotation = m_rotation.value();
    if (rotation.yaw() != 0.0)
        attributes.try_emplace("yaw", std::to_string(rotation.yaw()));
    if (rotation.pitch() != 0.0)
        attributes.try_emplace("pitch", std::to_string(rotation.pitch()));
    if (rotation.roll() != 0.0)
        attributes.try_emplace("roll", std::to_string(rotation.roll()));
    return attributes;
}

void RotateFeature::compute_and_update_ancestor_values(AncestorValues& ancestor_values)
{
    m_rotation.update_ancestor_values(ancestor_values);
}

void PaddingFeature::update_from_attributes(const AttributeMap& attributes)
{
    auto iter = attributes.find("padding");
    if (iter != attributes.end())
        m_padding.set_value(std::stof(iter->second));
}

AttributeMap PaddingFeature::attributes() const
{
    auto attributes = AttributeMap();
    attributes.try_emplace("padding", m_padding.string());
    return attributes;
}

void PaddingFeature::compute_and_update_ancestor_values(AncestorValues& ancestor_values)
{
    m_padding.update_ancestor_values(ancestor_values);
}

void SpacingFeature::update_from_attributes(const AttributeMap& attributes)
{
    auto iter = attributes.find("spacing");
    if (iter != attributes.end())
        m_spacing.set_value(std::stof(iter->second));
}

AttributeMap SpacingFeature::attributes() const
{
    auto attributes = AttributeMap();
    attributes.try_emplace("spacing", m_spacing.string());
    return attributes;
}

void SpacingFeature::compute_and_update_ancestor_values(AncestorValues& ancestor_values)
{
    m_spacing.update_ancestor_values(ancestor_values);
}

void AxisFeature::update_from_attributes(const AttributeMap& attributes)
{
    auto iter = attributes.find("axis");
    if (iter == attributes.end())
        return;

    m_axis.set_value(string_to_axis(iter->second.data()));
}

AttributeMap AxisFeature::attributes() const
{
    auto attributes = AttributeMap();
    attributes.try_emplace("axis", m_axis.string());
    return attributes;
}

void AxisFeature::compute_and_update_ancestor_values(AncestorValues& ancestor_values)
{
    m_axis.update_ancestor_values(ancestor_values);
}

void AlignFeature::update_from_attributes(const AttributeMap& attributes)
{
    auto iter = attributes.find("align");
    if (iter == attributes.end())
        return;

    m_alignment.set_value(string_to_alignment(iter->second.data()));
}

AttributeMap AlignFeature::attributes() const
{
    auto attributes = AttributeMap();
    attributes.try_emplace("align", m_alignment.string());
    return attributes;
}

void AlignFeature::compute_and_update_ancestor_values(AncestorValues& ancestor_values)
{
    m_alignment.update_ancestor_values(ancestor_values);
}

void CircularFeature::update_from_attributes(const AttributeMap& attributes)
{
    auto iter = attributes.find("radius");
    if (iter != attributes.end())
        m_radius.set_value(std::stof(iter->second));

    iter = attributes.find("detail");
    if (iter != attributes.end())
        m_detail.set_value(UnitInterval(std::stof(iter->second)));
}

AttributeMap CircularFeature::attributes() const
{
    auto attributes = AttributeMap();
    attributes.try_emplace("radius", m_radius.string());
    attributes.try_emplace("detail", m_detail.string());
    return attributes;
}

void CircularFeature::compute_and_update_ancestor_values(AncestorValues& ancestor_values)
{
    m_radius.update_ancestor_values(ancestor_values);
    m_detail.update_ancestor_values(ancestor_values);
}

size_t CircularFeature::num_circular_slices() const
{
    // We want to avoid slice blowup if someone (like me 5min ago) gives us 1.0 detail:
    // This formula was chosen because it graphed nice (and 10 is bare min to look like a circle)
    return static_cast<size_t>(std::log10(std::sqrt(detail() + 1.0f)) * radius() + 10);
}

float ScaleFeatureSet::compute_scale_factor(float width, float height, float depth) const
{
    assert(!std::isnan(width) && !std::isnan(height) && !std::isnan(depth));

    bool unconstrained_width = width_is_defaulted();
    bool unconstrained_height = height_is_defaulted();
    bool unconstrained_depth = depth_is_defaulted();
    if (unconstrained_width && unconstrained_height && unconstrained_depth)
        return 1.0f;

    auto [target_width, target_height, target_depth] = lengths();
    auto inf = std::numeric_limits<float>::infinity();
    float width_factor = (unconstrained_width || !std::isnormal(depth)) ? inf : (target_width / width);
    float height_factor = (unconstrained_height || !std::isnormal(height)) ? inf : (target_height / height);
    float depth_factor = (unconstrained_depth || !std::isnormal(depth)) ? inf : (target_depth / depth);
    assert(!std::isnan(width_factor) && !std::isnan(height_factor) && !std::isnan(depth_factor));

    if (axis_is_defaulted()) {
        auto calc_factor = std::min({ width_factor, height_factor, depth_factor });
        return calc_factor == inf ? 1.0f : calc_factor;
    }

    float factor = 1.0f;
    switch (axis()) {
    case Axis::X:
        factor = width_factor;
        break;
    case Axis::Y:
        factor = height_factor;
        break;
    case Axis::Z:
        factor = depth_factor;
        break;
    default:
        assert(false);
    }

    assert(std::isnormal(factor));
    return factor;
}

void JuxtaposeFeatureSet::juxtapose(const std::vector<Path>& paths, std::shared_ptr<RenderTree>& render_tree) const
{
    auto our_axis = axis();
    auto offset_pt = Point();

    size_t i = 0;
    for (const auto& path : paths) {
        auto bounds = render_tree->positioned_bounds_of(path).strip_pos();
        render_tree->move_parent_and_descendants_by(path, offset_pt);

        auto our_spacing = i++ != paths.size() - 1 ? spacing() : 0.0f;
        switch(our_axis) {
        case Axis::X:
            offset_pt.x += bounds.width() + our_spacing;
            break;
        case Axis::Y:
            offset_pt.y += bounds.height() + our_spacing;
            break;
        case Axis::Z:
            offset_pt.z += bounds.depth() + our_spacing;
            break;
        }
    }
}

static float offset_from_alignment(Alignment align, Axis axis, const Bounds& bounds, const Bounds& total_bounds)
{
    switch (align) {
    case Alignment::Left:
        return (total_bounds.bottom_left()[axis] - bounds.bottom_left()[axis]);
    case Alignment::Right:
        return (total_bounds.bottom_right()[axis] - bounds.bottom_right()[axis]);
    case Alignment::Center:
        return (total_bounds.center()[axis] - bounds.center()[axis]);
    }

    assert(false);
    return 0.0;
}

void JuxtaposeFeatureSet::center_within_axis_length(const std::vector<Path>& paths, std::shared_ptr<RenderTree>& render_tree, Axis our_axis) const
{
    auto num_children = paths.size();
    if (num_children == 0)
        return;

    auto total_bounds = Bounds();
    for (const auto& path : paths)
        total_bounds += render_tree->positioned_bounds_of(path);

    auto total_length = total_bounds.axis_length(our_axis);
    auto target_length = axis_length(our_axis);
    auto remaining_space = target_length - total_length;

    auto offset = Point();
    offset[our_axis] = remaining_space / 2;

    float i = 0;
    for (const auto& path : paths) {
        render_tree->move_parent_and_descendants_by(path, offset);
        i++;
    }
}

void JuxtaposeFeatureSet::align(const std::vector<Path>& paths, std::shared_ptr<RenderTree>& render_tree, const Bounds& total_pos_bounds, Axis our_axis, Alignment our_alignment) const
{
    auto num_children = paths.size();
    if (num_children == 0)
        return;

    for (const auto& path : paths) {
        const auto& pos_bounds = render_tree->positioned_bounds_of(path);

        // FIXME: We should allow for a secondary alignment to be specified
        auto offset = Point();
        switch(our_axis) {
        case Axis::X:
            offset.z += offset_from_alignment(our_alignment, Axis::Z, pos_bounds, total_pos_bounds);
            break;
        case Axis::Y:
            offset.x += offset_from_alignment(our_alignment, Axis::X, pos_bounds, total_pos_bounds);
            offset.z += offset_from_alignment(our_alignment, Axis::Z, pos_bounds, total_pos_bounds);
            break;
        case Axis::Z:
            offset.x += offset_from_alignment(our_alignment, Axis::X, pos_bounds, total_pos_bounds);
            break;
        }

        render_tree->move_parent_and_descendants_by(path, offset);
    }
}

Bounds JuxtaposeFeatureSet::positioned_bounds_with_provided_lengths(const std::vector<Path>& paths, std::shared_ptr<RenderTree>& render_tree) const
{
    // If we recieve additional axis lengths e.g. width, height, depth, align,
    // use those instead of bounds
    auto total_bounds = Bounds();
    for (const auto& path : paths)
        total_bounds += render_tree->get(path)->positioned_bounds();

    auto base = total_bounds.base();
    auto end = total_bounds.end();
    if (!width_is_defaulted()) {
        end.x = base.x + width();
        total_bounds = Bounds { base, end };
    }
    if (!height_is_defaulted()) {
        end.y = base.y + height();
        total_bounds = Bounds { base, end };
    }
    if (!depth_is_defaulted()) {
        end.z = base.z + depth();
        total_bounds = Bounds { base, end };
    }

    return total_bounds;
}


}
