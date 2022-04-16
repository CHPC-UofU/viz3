// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <memory>
#include <utility>

#include "feature.hpp"
#include "render.hpp"

namespace viz3 {

/*
 * An Element sits in a tree hierarchy, defined by the Node class. Each
 * Element is responsible for two things via the render() function:
 *   1. Producing a geometry (Geometry class) based on key-value attributes
 *      stored in Feature mixin classes and based the geometries of their
 *      children. The attributes of Features can be dynamically set and be
 *      manipulated by the user, influencing the resulting geometry upon the
 *      next render().
 *   2. Manipulating the geometry of children geometries and positioning them.
 *      Operations on geometries, such as move and rotate, are applied to all
 *      descendants.
 *
 * Thus, the render() function is called on each Element by the Node tree in a
 * bottom up fashion, with each descendant Element producing a geometry based
 * on their attributes and based on information stored in children geometries.
 * The resulting geometry tree represents a 3D scene, which can be drawn.
 *
 * To facilitate top-down constraints, such as a fixed size, Feature
 * attributes may optionally refer to ancestor attribute values within the
 * Node/Element tree. Ancestor attributes are stored in a AncestorValues
 * object, which this Element should update with the update_ancestor_values()
 * function when called.
 *
 *
 * Developer Notes:
 * ---
 * We'll use the CRTP pattern here because we want subclasses of
 * Element to automatically be copyable (required for the run-time template
 * logic in Node), _but also enforce that the copy be a shared_ptr()_. When
 * std::enabled_shared_from_this is used, all instances of a class *must be
 * created from a shared ptr*, which is why things are implemented this way.
 *
 * The way this works is by having clone() act as our copy constructor, but
 * returning a shared_ptr of the object instead of an object. Behind the scenes
 * this clone() will simply call the copy constructor of the derived type (passed
 * in by a template) and return that in a shared pointer.
 *
 * Here, we have both an AbstractElement and a BaseElement. The second is
 * meant to be inherited, with the subclass name provided to the derived subclass
 * template. This template prevents us from generically referring to an Element(),
 * so that is why a AbstractElement is used (and BaseElement inherits from it).
 *
 * https://en.wikipedia.org/wiki/Curiously_recurring_template_pattern
 */
class AbstractElement : public std::enable_shared_from_this<AbstractElement> {
public:
    AbstractElement(std::string name)
        : std::enable_shared_from_this<AbstractElement>()
        , m_name(std::move(name)) {};

    virtual ~AbstractElement() = default;
    virtual std::shared_ptr<AbstractElement> clone() const = 0;

    virtual const std::string& get_name() const { return m_name; }
    virtual void set_name(const std::string& name) { m_name = name; }

    /*
     * Render is the core function of the viz3 framework. Each Element should
     * a) position their children geometries (Geometry), if needed
     * b) manipulate their children geometries (Geometry), if needed
     * c) create and set their own Geometry, if needed
     *
     * The RenderTree holds all geometries (Geometry class) in a tree hierarchy
     * reflecting the Element Node hierarchy.
     *
     * Updating geometries should be done by calling functions of the
     * RenderTree, which, for operations such as move, will recursively apply
     * such operation to all descendants. The Path given is the key used to
     * select/update a sub-hierarchy of geometries.
     *
     * An Element need not provide a Geometry, if e.g. it has no corresponding
     * mesh and simply positions it's children.
     */
    virtual void render(const Path&, std::shared_ptr<RenderTree>) const {};

    /*
     * Any attributes accessible to sub-Elements that can be used for relative
     * attribute calculations (e.g. width="10" in parent Element, width="100%"
     * in a descendant Element) are updated in the AncestorValues object here.
     */
    virtual void update_ancestor_values(AncestorValues&) {};

    /*
     * Updates the Element's attributes from a attribute map (string-to-string
     * map). If any attributes are relative, their computed values should be
     * reflected in the updated attribute object.
     *
     * For super dumb historical reasons this is non-const because of trickery
     * in Relative*Value classes (within values.hpp) that caches computations
     * here. I don't have time to fix this blight sorry.
     */
    virtual void update_from_attributes(AttributeMap&) = 0;
    /*
     * Returns the attributes of the Element in string form.
     */
    virtual AttributeMap attributes() const { return AttributeMap(); };

protected:
    AbstractElement(const AbstractElement&) = default;

private:
    std::string m_name;
};

/*
 * This subclass should be the basis for all Element()s, though
 * AbstractElement may be used to store and refer to any Element(). It
 * provides a clone() mechanism. If any sub-Element() has any additional data
 * that needs to be copied, it must implement a copy constructor, but need not
 * override clone() (clone() will simply call the copy constructor).
 *
 * Subclasses of Element may inherit from Feature mixins, which provide certain
 * values/attributes and code features and facilitates the reuse of certain
 * behaviors across Element()s, as well as relative values (see values.hpp
 * for details).
 *
 * e.g. BoxElement : public BaseElement<BoxElement>, SizeFeature { ...
 *
 * These Feature()s provide an update_ancestor_values() and attributes() method
 * that can be used in our Element() update_ancestor_values() method. Rather than
 * forcing each sub-Element to call Feature::update_ancestor_values() and
 * Feature::attributes() for every feature, we do some template magic to call
 * that method for every Feature provided to the template.
 *
* e.g. BoxElement : public BaseElement<BoxElement, SizeFeature> { ...
*      provides a floating point based width, height, and depth attribute that
*      can refer to ancestor values in the Node/Element hierarchy.
 */
template <class DerivedElement, class... Features>
class BaseElement : public AbstractElement, public FeatureSet<Features...> {
public:
    BaseElement(std::string name, const AttributeMap& attributes)
        : AbstractElement(std::move(name))
        , FeatureSet<Features...>(attributes) {};

    std::shared_ptr<AbstractElement> clone() const override
    {
        return std::make_shared<DerivedElement>(static_cast<DerivedElement const&>(*this));
    }

    void update_ancestor_values(AncestorValues& ancestor_values) override
    {
        FeatureSet<Features...>::compute_and_update_ancestor_values(ancestor_values);
    }

    void update_from_attributes(AttributeMap& attributes) override
    {
        FeatureSet<Features...>::update_from_attributes(attributes);
    }

    AttributeMap attributes() const override
    {
        return FeatureSet<Features...>::attributes();
    }
};

class NopElement : public BaseElement<NopElement, NopFeature> {
public:
    using BaseElement::BaseElement;
    NopElement(std::string name)
        : BaseElement(std::move(name), {}) {};

    // This is defaulted to do nothing because we use empty Element()s in
    // places where we don't actually want to use the Element in question, but
    // we don't want to special case it.
    void render(const Path&, std::shared_ptr<RenderTree>) const override {};
};

/*
 * Helper CRTP Element that provides all the common Features used to produce a
 * mesh.
 */
template <class DerivedElement, class... OtherFeatures>
class MeshElement : public BaseElement<DerivedElement, OtherFeatures..., TextFeature, ColorFeature, OpticsFeature, HideShowFeature> {
public:
    using BaseElement<DerivedElement, OtherFeatures..., TextFeature, ColorFeature, OpticsFeature, HideShowFeature>::BaseElement;

    // FIXME? Maybe we should just make a MeshFeatureSet instead, so we don't
    //        have to have this in a template, or even has this class?
    Geometry construct_geometry(std::vector<Point>&& vertexes, std::vector<Face>&& faces, const Point& pos) const
    {
        return Geometry {
            vertexes,
            faces,
            pos,
            this->compute_color(this->opacity()),
            this->hide_distance(),
            this->show_distance(),
            this->text(),
        };

    }
};

}
