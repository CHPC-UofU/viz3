// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <algorithm>
#include <limits>
#include <string>
#include <unordered_map>
#include <utility>

#include "value_types.hpp"
#include "color.hpp"
#include "rotation.hpp"
#include "value.hpp"
#include "path.hpp"
#include "render.hpp"

/*
 * This header defines a bunch of "Features", that is, particular collections of
 * values and logic that Elements can use. Features are constructed from an
 * attribute map, a map of string names to string values. The values are likely
 * to be converted from a string form to a better type internally within a
 * feature (e.g. a float).
 *
 * Within the context of viz3, the attribute map given to features is roughly
 * the key=value pair map from an XML element.
 * e.g. '<sphere radius="10" color="blue"/>' maps to an SphereElement() and an
 *      sphere element may have a RadiusFeature constructed from the 'radius'
 *      part of the map, as well as a ColorFeature constructed from the 'color'
 *      part of the map.
 *
 * Each Feature should have five things:
 *   1. A protected default constructor (which means that member variables should
 *      have a default, valid, state)
 *   2. A public 'const AttributeMap&' constructor
 *   3. An update_from_attributes(const AttributeMap&) method
 *   4. An 'AttributeMap attributes()' method, which returns a string form of
 *      the internal variables (e.g. for outputting to XML again).
 *   5. A compute_and_update_from_ancestor_values(AncestorValues&) method,
 *      which updates the current state based on ancestor values. See value.hpp
 *      for details.
 *
 * Parts 1-2 are provided by the FEATURE_ATTR_CTOR macro, which should be
 * placed directly under the 'class ...' definition.
 */

#define FEATURE_ATTR_CTOR(Feature) \
    protected:                              \
    Feature() = default;                    \
    public:                                 \
    Feature(const AttributeMap& attributes) \
        : Feature()                         \
    {                                       \
        update_from_attributes(attributes); \
    }

namespace viz3 {

using AttributeMap = std::unordered_map<std::string, std::string>;

class TextFeature {
    FEATURE_ATTR_CTOR(TextFeature);

public:
    void update_from_attributes(const AttributeMap&);
    AttributeMap attributes() const;

    void compute_and_update_ancestor_values(AncestorValues&);

    void set_text(const std::string& text) { m_text.set_value(text); }
    std::string text() const { return m_text.value(); }

private:
    StringValue m_text = { "text", "text", "", true };
};

inline const float default_width = 1.0f;
inline const float default_height = 1.0f;
inline const float default_depth = 1.0f;

class SizeFeature {
    FEATURE_ATTR_CTOR(SizeFeature);

public:
    void update_from_attributes(const AttributeMap&);
    AttributeMap attributes() const;

    void compute_and_update_ancestor_values(AncestorValues&);

    void set_width(float width) { m_width.set_value(std::max<float>(width, 0.0)); };
    float width() const { return m_width.value(); }
    bool width_is_defaulted() const { return m_width.is_defaulted(); }

    void set_height(float height) { m_height.set_value(std::max<float>(height, 0.0)); };
    float height() const { return m_height.value(); }
    bool height_is_defaulted() const { return m_height.is_defaulted(); }

    void set_depth(float depth) { m_depth.set_value(std::max<float>(depth, 0.0)); };
    float depth() const { return m_depth.value(); }
    bool depth_is_defaulted() const { return m_depth.is_defaulted(); }

    std::tuple<float, float, float> lengths() const
    {
        return { width(), height(), depth() };
    }

    float axis_length(Axis axis) const
    {
        switch (axis) {
        case Axis::X:
            return width();
        case Axis::Y:
            return height();
        case Axis::Z:
            return depth();
        }
        assert(false);
        return 0.0;
    }
    bool axis_length_is_defaulted(Axis axis) const
    {
        switch (axis) {
        case Axis::X:
            return width_is_defaulted();
        case Axis::Y:
            return height_is_defaulted();
        case Axis::Z:
            return depth_is_defaulted();
        }
        assert(false);
        return false;
    }

private:
    // Note: These need to be topologically sorted in
    //       compute_and_update_ancestor_values() to prevent failure when
    //       users attept to make values relative to others
    RelativeFloatValue m_width = {"width", "w", default_width, true };
    RelativeFloatValue m_height = {"height", "h", default_height, true };
    RelativeFloatValue m_depth = {"depth", "d", default_depth, true };
};

class ColorFeature {
    FEATURE_ATTR_CTOR(ColorFeature);

public:
    void update_from_attributes(const AttributeMap&);
    AttributeMap attributes() const;

    void compute_and_update_ancestor_values(AncestorValues&);

    void set_color(color::RGBA color) { m_color.set_value(color); }
    color::RGBA color() const { return m_color.value(); }
    void set_darkness(float darkness) { m_darkness.set_value(darkness); }
    float darkness() const { return m_darkness.value(); }

    color::RGBA compute_color(float opacity) const;

private:
    ColorValue m_color { "color", "c", color::default_color, true };
    UnitIntervalValue m_darkness { "darkness", "darkness", 0.0, true };
};

class OpticsFeature {
    FEATURE_ATTR_CTOR(OpticsFeature);

public:
    void update_from_attributes(const AttributeMap&);
    AttributeMap attributes() const;

    void compute_and_update_ancestor_values(AncestorValues&);

    // Note: we return floats, rather than UnitInterval, to make it easier to
    //       get the floating point value in Python
    void set_opacity(float opacity) { m_opacity.set_value(opacity); }
    float opacity() const { return m_opacity.value(); }

private:
    UnitIntervalValue m_opacity { "opacity", "o", 1.0, true };
};

class HideShowFeature {
    FEATURE_ATTR_CTOR(HideShowFeature);

public:
    void update_from_attributes(const AttributeMap&);
    AttributeMap attributes() const;

    void compute_and_update_ancestor_values(AncestorValues&);

    void set_hide_distance(float hide_distance) { m_hide_distance.set_value(hide_distance); }
    float hide_distance() const { return m_hide_distance.value(); }
    void set_show_distance(float show_distance) { m_show_distance.set_value(show_distance); }
    float show_distance() const { return m_show_distance.value(); }
    std::tuple<float, float> hide_and_show_distances() const { return { hide_distance(), show_distance() }; }

    void set_clamp_descendant_hide_distances(bool should) { m_clamp_descendant_hide_distances.set_value(should); };
    bool clamp_descendant_hide_distances() const { return m_clamp_descendant_hide_distances.value(); }

    void set_clamp_descendant_show_distances(bool should) { m_clamp_descendant_show_distances.set_value(should); };
    bool clamp_descendant_show_distances() const { return m_clamp_descendant_show_distances.value(); }

private:
    FloatValue m_hide_distance { "hide_distance", "hide_distance", 0.0, true };
    FloatValue m_show_distance { "show_distance", "show_distance", std::numeric_limits<float>::infinity(), true };
    BoolValue m_clamp_descendant_hide_distances { "clamp_descendant_hide_distances", "clamp_descendant_show_distances", false, true };
    BoolValue m_clamp_descendant_show_distances { "clamp_descendant_show_distances", "clamp_descendant_show_distances", false, true };
};

class RotateFeature {
    FEATURE_ATTR_CTOR(RotateFeature);

public:
    void update_from_attributes(const AttributeMap&);
    AttributeMap attributes() const;

    void compute_and_update_ancestor_values(AncestorValues&);

    void set_rotation(Rotation rotation) { m_rotation.set_value(rotation); }
    Rotation rotation() const { return m_rotation.value(); }

private:
    RotationValue m_rotation { "rotation", "rotation", Rotation(0), true };
};

class PaddingFeature {
    FEATURE_ATTR_CTOR(PaddingFeature);

public:
    void update_from_attributes(const AttributeMap&);
    AttributeMap attributes() const;

    void compute_and_update_ancestor_values(AncestorValues&);

    void set_padding(float padding) { m_padding.set_value(padding); }
    float padding() const { return m_padding.value(); }

private:
    RelativeFloatValue m_padding = { "padding", "p", 0.0f, true };
};

class SpacingFeature {
    FEATURE_ATTR_CTOR(SpacingFeature);

public:
    void update_from_attributes(const AttributeMap&);
    AttributeMap attributes() const;

    void compute_and_update_ancestor_values(AncestorValues&);

    void set_spacing(float spacing) { m_spacing.set_value(spacing); }
    float spacing() const { return m_spacing.value(); }

private:
    RelativeFloatValue m_spacing = { "spacing", "s", 0.0f, true };
};

class AxisFeature {
    FEATURE_ATTR_CTOR(AxisFeature);

public:
    void update_from_attributes(const AttributeMap&);
    AttributeMap attributes() const;

    void compute_and_update_ancestor_values(AncestorValues&);

    void set_axis(Axis axis) { m_axis.set_value(axis); }
    Axis axis() const { return m_axis.value(); }
    bool axis_is_defaulted() const { return m_axis.is_defaulted(); }

private:
    AxisValue m_axis = { "axis", "axis", Axis::X, true };
};

class AlignFeature {
    FEATURE_ATTR_CTOR(AlignFeature);

public:
    void update_from_attributes(const AttributeMap&);
    AttributeMap attributes() const;

    void compute_and_update_ancestor_values(AncestorValues&);

    void set_alignment(Alignment align) { m_alignment.set_value(align); }
    Alignment alignment() const { return m_alignment.value(); }

private:
    AlignmentValue m_alignment = { "align", "align", Alignment::Center, true };
};

inline const UnitInterval default_detail = 0.5f;

class CircularFeature {
    FEATURE_ATTR_CTOR(CircularFeature);

public:
    void update_from_attributes(const AttributeMap&);
    AttributeMap attributes() const;

    void compute_and_update_ancestor_values(AncestorValues&);

    void set_radius(float radius) { m_radius.set_value(radius); }
    float radius() const { return m_radius.value(); }

    void set_detail(float detail) { m_detail.set_value(UnitInterval(detail)); }
    float detail() const { return m_detail.value(); }

    size_t num_circular_slices() const;

private:
    RelativeFloatValue m_radius = { "radius", "r", 1.0f, true };
    FloatValue m_detail = { "detail", "detail", default_detail, true };
};

// A Feature that has no features/functions; used as a hack for NopElement,
// since FeatureSet requires at least one Feature
// FIXME: Replace with template specialization in BaseElement()
class NopFeature {
    FEATURE_ATTR_CTOR(NopFeature);

public:
    void update_from_attributes(const AttributeMap&) {};
    AttributeMap attributes() const { return {}; };

    void compute_and_update_ancestor_values(AncestorValues&) {};
};

/*
 * Defines a generic set of features and generates Feature::* methods that call
 * each feature. Requires at least one Feature (NopFeature may be used in the
 * empty case).
 *
 * For an overview of variadic templates, see:
 * https://eli.thegreenplace.net/2014/variadic-templates-in-c/
 * and for C++17 fold expressions, see:
 * https://en.cppreference.com/w/cpp/language/fold
 */
template <class... Features>
class FeatureSet : public Features... {
protected:
    FeatureSet() = default;

public:
    FeatureSet(const AttributeMap& attributes)
        : FeatureSet()
    {
        (Features::update_from_attributes(attributes), ...);
    }

    void update_from_attributes(const AttributeMap& attributes)
    {
        (Features::update_from_attributes(attributes), ...);
    }

    AttributeMap attributes() const
    {
        return attributes<Features...>();
    }
    void compute_and_update_ancestor_values(AncestorValues& ancestor_values)
    {
        (Features::compute_and_update_ancestor_values(ancestor_values), ...);
    }

private:
    template <class FirstFeature, class... RestFeatures>
    AttributeMap attributes() const
    {
        auto attributes = FirstFeature::attributes();
        (attributes.merge(RestFeatures::attributes()), ...);
        return attributes;
    }
};

class ScaleFeatureSet : public FeatureSet<SizeFeature, AxisFeature> {
public:
    using FeatureSet::FeatureSet;

    float compute_scale_factor(float width, float height, float depth) const;
};

class JuxtaposeFeatureSet : public FeatureSet<SizeFeature, AxisFeature, SpacingFeature, AlignFeature> {
public:
    using FeatureSet::FeatureSet;

    void juxtapose(const std::vector<Path>&, std::shared_ptr<RenderTree>&) const;
    void center_within_axis_length(const std::vector<Path> &paths, std::shared_ptr<RenderTree> &render_tree, Axis our_axis) const;
    void align(const std::vector<Path>&, std::shared_ptr<RenderTree>&, const Bounds&, Axis, Alignment) const;
    Bounds positioned_bounds_with_provided_lengths(const std::vector<Path>&, std::shared_ptr<RenderTree>&) const;
};

}
