// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <memory>
#include <ostream>
#include <string>
#include <utility>
#include <vector>

#include "element.hpp"
#include "path.hpp"
#include "render.hpp"
#include "value.hpp"

namespace viz3 {

// Aliasing these here allows us to do special things with these "templates" in
// the future without having to chase down what Nodes are actually templated.
// We also get some type safety here since they appear as different types.
class Node;
using TemplateNode = Node;

/*
 * A node in a tree data structure. Each node has an associated Element().
 *
 * These classes are reference counted (std::shared_from_this) since we allow
 * users to modify them and they may keep them around for arbitrarily long.
 */
class Node : public std::enable_shared_from_this<Node> {
public:
    // Virtual destructors are so that subclasses held in a Node* (or shared_ptr)
    // get _their_ destructor called via dispatch, rather than the base Node
    virtual ~Node() = default;

    // Make constructor private so the only way to instantiate this class is to
    // use this method, which returns a shared_ptr. We absolutely need a
    // shared pointer since we are using std::enable_shared_from_this<>
    static std::shared_ptr<Node> construct(std::shared_ptr<AbstractElement> element, std::shared_ptr<Node> parent, std::shared_ptr<RenderTree> render_tree) {
        // cannot use make_shared due to private constructor
        return std::shared_ptr<Node>(new Node(std::move(element), std::move(parent), std::move(render_tree)));
    }

    // Subclasses will need to override this and do their own cloning.
    virtual std::shared_ptr<Node> clone_into_parent(const std::string& new_name, std::shared_ptr<Node> new_parent) {
        auto new_node = std::shared_ptr<Node>(new Node(*this)); // copy
        new_node->set_name(new_name);
        new_node->set_parent(new_parent);

        // Inside the copy ctor we cannot copy our children since that would require
        // a  back shared_ptr<> for each children's parent. So we copy here instead.
        new_node->copy_children_from_node(shared_from_this());
        return new_node;
    }

    bool is_root() const { return m_parent.get() == nullptr; }
    Path path() const
    {
        return is_root() ? Path {} : (m_parent->path() + get_name());
    }
    bool operator==(const Node& other) const
    {
        return path() == other.path();
    }
    bool operator!=(const Node& other) const
    {
        return !(*this == other);
    }

    virtual const std::string& get_name() const { return m_element->get_name(); }

    std::shared_ptr<AbstractElement> element();
    void set_element(std::shared_ptr<AbstractElement>);

    std::shared_ptr<Node> parent() const { return m_parent; }

    // Make the construct_ method public, instead of add_, since the creation
    // of a Node is the concern of our 'friend class'(es) and ourselves, not
    // the user of the tree
    std::shared_ptr<Node> construct_child(std::shared_ptr<AbstractElement> element);
    void remove_child(const std::string&);
    bool has_child(const std::string& with_name) const;
    std::optional<std::shared_ptr<Node>> try_get_child(const std::string& with_name) const;
    std::shared_ptr<Node> find_descendant(const Path& path);
    std::vector<std::string> children_names() const;
    std::vector<std::shared_ptr<Node>> children() const { return m_children; };

    std::shared_ptr<TemplateNode> construct_template(std::shared_ptr<AbstractElement>);
    std::optional<std::shared_ptr<TemplateNode>> try_get_template(const std::string&);
    std::optional<std::shared_ptr<Node>> try_make_template(const std::string&, const std::string&);
    std::optional<std::shared_ptr<Node>> try_get_child_or_make_template(const std::string&, const std::string&);
    std::vector<std::string> template_names() const;
    std::vector<std::shared_ptr<TemplateNode>> templates() const { return m_templates; };

    std::string string() const;

    friend std::ostream& operator<<(std::ostream&, const Node&);
    friend class NodeTransaction;
    friend class LayoutEngine;

protected:
    Node(std::shared_ptr<AbstractElement> element, std::shared_ptr<Node> parent, std::shared_ptr<RenderTree> render_tree)
        : std::enable_shared_from_this<viz3::Node>()
        , m_parent(std::move(parent))
        , m_element(std::move(element))
        , m_render_tree(std::move(render_tree))
        , m_template_insertion_indexes()
        , m_templates()
        , m_children() {};

    Node(const Node& other)
        : std::enable_shared_from_this<viz3::Node>()
        , m_parent(other.m_parent)
        , m_element(other.m_element->clone())
        , m_render_tree(other.m_render_tree)
        , m_template_insertion_indexes()
        , m_templates()
        , m_children() {};

    /*
     * A method that calls render() on all sub-elements. Basically the crux of
     * this class.
     */
    virtual void render(AncestorValues&);

    void copy_children_from_node(std::shared_ptr<Node> other_node);

    void add_child(std::shared_ptr<Node> node);
    void add_template(std::shared_ptr<TemplateNode> template_node);

    // Used only for cloning; name should be fixed for users
    virtual void set_name(const std::string& new_name) { m_element->set_name(new_name); };
    void set_parent(std::shared_ptr<Node> new_parent) {
        // FIXME: We don't have to invalidate everything, just our siblings...
        m_render_tree->invalidate_parent_and_child_pos(path().without_last());
        m_parent = std::move(new_parent);
    }

    std::shared_ptr<RenderTree> render_tree() const { return m_render_tree; }

    void update_hierarchical_ancestor_values(AncestorValues&) const;

private:
    void add_child(std::shared_ptr<Node> node, std::optional<size_t> insertion_index);
    void insert_rendered_bounds_from_children();

    void string_impl(std::ostream&, unsigned int indent = 0) const;

    /*
     * With m_template_*_insertion_indexes we seek to ensure that the order of
     * stored nodes (m_children) is based on the order of both template
     * additions and node additions, rather than just the order of node
     * construction. This means that if a template is added before a particular
     * node, then nodes constructed from that template are always before that
     * particular node.
     *
     * e.g.
     *
     * construct_child("first");
     * construct_template("second_template");
     * construct_child("third");
     * make_template("second_template", "second_first")
     *
     * results in:
     * ["first", "second_first", "third"]
     * rather than:
     * ["first", "third", "second_first"]
     *
     * This is helpful for our 3D expansion capabilities, since we can define
     * what the tree should look like upfront (e.g. in XML) with a mix of
     * templates and nodes and then just make new nodes from those templates
     * later, without having to worry about maintaining the order originally
     * defined.
     */
    size_t compute_child_insertion_index(const std::string&);

    std::shared_ptr<Node> m_parent;
    std::shared_ptr<AbstractElement> m_element;
    std::shared_ptr<RenderTree> m_render_tree;
    std::vector<size_t> m_template_insertion_indexes;
    std::vector<std::shared_ptr<TemplateNode>> m_templates;
    std::vector<std::shared_ptr<Node>> m_children;
};

/*
 * Root node with a special render_from_root() method, since render() relies
 * on some values that aren't present when we start rendering (and we want to
 * keep that stuff to ourself)
 */
class RootNode final : public Node {
public:
    static std::shared_ptr<RootNode> construct(std::shared_ptr<RenderTree> render_tree) {
        // cannot use make_shared due to private constructor
        return std::shared_ptr<RootNode>(new RootNode(std::move(render_tree)));
    }
    void render_from_root();

private:
    RootNode(std::shared_ptr<RenderTree> render_tree)
        : Node(std::make_shared<NopElement>(""), std::shared_ptr<Node>(), std::move(render_tree)) {};
};

}
