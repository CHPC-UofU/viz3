// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <algorithm>
#include <cassert>
#include <memory>
#include <ostream>
#include <string>

#include "node.hpp"


namespace viz3 {

std::ostream& operator<<(std::ostream& os, const Node& node)
{
    node.string_impl(os);
    return os;
}

std::string Node::string() const
{
    std::stringstream stream {};
    string_impl(stream);
    return stream.str();
}

static void indent_stream(std::ostream& os, unsigned int indent)
{
    for (unsigned int i = 0; i < indent; i++)
        os << "\t";
}

void Node::string_impl(std::ostream& os, unsigned int indent) const
{
    indent_stream(os, indent);
    os << "Node '" << get_name() << "' ("<< std::endl;

    indent_stream(os, indent + 1);
    os << "templates: <";

    auto node_templates = templates();
    if (!node_templates.empty()) {
        os << std::endl;
        for (size_t i = 0; i < node_templates.size(); i++) {
            node_templates[i]->string_impl(os, indent + 2);
            if (i != node_templates.size() - 1)
                os << ", ";

            os << std::endl;
        }
        indent_stream(os, indent + 1);
    }
    os << ">) {" << std::endl;

    auto node_children = children();
    if (!node_children.empty()) {
        os << std::endl;
        for (size_t i = 0; i < node_children.size(); i++) {
            node_children[i]->string_impl(os, indent + 1);
            if (i != node_children.size() - 1)
                os << ", ";

            os << std::endl;
        }
        indent_stream(os, indent);
    }
    os << "}";
}

void Node::copy_children_from_node(std::shared_ptr<Node> other_node)
{
    for (const auto& child_node : other_node->children())
        add_child(child_node->clone_into_parent(child_node->get_name(), shared_from_this()));

    for (const auto& template_node : other_node->templates())
        add_template(std::dynamic_pointer_cast<TemplateNode>(template_node->clone_into_parent(template_node->get_name(), shared_from_this())));

    m_template_insertion_indexes = other_node->m_template_insertion_indexes;
}

std::shared_ptr<AbstractElement> Node::element()
{
    // FIXME: This is ugly; we require this because the user may arbirarily
    //        modify the element (such as changing attributes like width),
    //        causing us to assume that we will have to re-render this element
    //        and all sub-elements
    m_render_tree->invalidate_parent_and_child_pos(path());
    return m_element;
}

void Node::set_element(std::shared_ptr<AbstractElement> element)
{
    // FIXME: See element()
    m_render_tree->invalidate_parent_and_child_pos(path());
    m_element = std::move(element);
}

size_t Node::compute_child_insertion_index(const std::string& with_name)
{
    // FIXME: Use try_get_* here, and change return of try_get to be an iterator!
    for (size_t i = 0; i < m_templates.size(); i++)
        if (m_templates[i]->get_name() == with_name)
            return m_template_insertion_indexes[i];

    assert(false);
    return m_children.size();
}

std::optional<std::shared_ptr<TemplateNode>> Node::try_get_template(const std::string& with_name)
{
    for (auto& template_node : m_templates)
        if (template_node->get_name() == with_name)
            return { template_node };
    return {};
}

std::shared_ptr<Node> Node::construct_child(std::shared_ptr<AbstractElement> element)
{
    auto node = Node::construct(std::move(element), shared_from_this(), render_tree());
    add_child(node);
    return node;
}

std::shared_ptr<TemplateNode> Node::construct_template(std::shared_ptr<AbstractElement> element)
{
    auto node = TemplateNode::construct(std::move(element), shared_from_this(), render_tree());
    add_template(node);
    return node;
}

std::optional<std::shared_ptr<Node>> Node::try_make_template(const std::string& template_name, const std::string& new_name)
{
    auto maybe_template = try_get_template(template_name);
    if (!maybe_template.has_value())
        throw std::invalid_argument("Could not find template with name " + template_name);

    auto constructed_child = maybe_template.value()->clone_into_parent(new_name, shared_from_this());
    auto insertion_index = compute_child_insertion_index(template_name);
    add_child(constructed_child, insertion_index);
    return constructed_child;
}

std::optional<std::shared_ptr<Node>> Node::try_get_child_or_make_template(const std::string& template_name, const std::string& new_name)
{
    auto maybe_child = try_get_child(new_name);
    if (maybe_child.has_value())
        return maybe_child;

    return try_make_template(template_name, new_name);
}

void Node::add_template(std::shared_ptr<TemplateNode> template_node)
{
    assert(std::all_of(m_templates.begin(), m_templates.end(), [&](auto& node) { return template_node != node; }));
    m_template_insertion_indexes.push_back(m_children.size());
    m_templates.push_back(std::move(template_node));
}

std::vector<std::string> Node::template_names() const
{
    std::vector<std::string> names;
    names.reserve(m_templates.size());

    for (const auto& template_node : m_templates)
        names.push_back(template_node->get_name());

    return names;
}

std::optional<std::shared_ptr<Node>> Node::try_get_child(const std::string& with_name) const
{
    for (auto& child : m_children)
        if (child->get_name() == with_name)
            return { child };
    return {};
}

void Node::add_child(std::shared_ptr<Node> node, std::optional<size_t> maybe_insertion_index)
{
    assert(node);

    // Cannot have duplicate names
    // FIXME: Maybe we should throw instead of asserting, since that is a user
    //        problem, not ours?
    assert(std::all_of(m_children.begin(), m_children.end(), [&](auto& child_node) { return child_node->get_name() != node->get_name(); }));

    assert(node->parent().get() == shared_from_this().get());
    auto node_children = node->children();
    assert(std::all_of(node_children.begin(), node_children.end(), [&](const auto& child_node) { return child_node->parent().get() == node.get(); }));

    // using optional because appending to the end has different implications for
    // insertion_indexes than inserting when insertion_index = 0
    if (maybe_insertion_index) {
        auto insertion_index = *maybe_insertion_index;
        assert(insertion_index <= m_children.size());

        auto insertion_iter = m_children.begin() + insertion_index;
        for (auto& template_insertion_index : m_template_insertion_indexes)
            // +1 -> insertion_index points after
            if (template_insertion_index >= insertion_index)
                template_insertion_index += 1;

        m_children.insert(insertion_iter, node);
    }
    else {
        m_children.push_back(node);
    }

    render_tree()->invalidate_parent_and_child_pos(path());
    std::string node_name = node->get_name();
}

void Node::add_child(std::shared_ptr<Node> node)
{
    add_child(std::move(node), {});
}

void Node::remove_child(const std::string& with_name)
{
    auto remove_pos = std::remove_if(m_children.begin(), m_children.end(), [&](const auto& child) { return child->get_name() == with_name; });
    if (remove_pos == m_children.end())
        return;

    size_t remove_index = m_children.end() - remove_pos;
    for (auto& insertion_index : m_template_insertion_indexes)
        if (insertion_index >= remove_index)
            insertion_index -= 1;

    m_children.erase(remove_pos);
    render_tree()->invalidate_parent_and_child_pos(path());
}

std::shared_ptr<Node> Node::find_descendant(const Path& path)
{
    for (const auto& child_node : m_children) {
        if (child_node->get_name() != path.first())
            continue;

        return path.is_leaf() ? child_node : child_node->find_descendant(path.without_first());
    }

    if (path.is_leaf() && get_name() == path.first())
        return shared_from_this();

    return {};
}

bool Node::has_child(const std::string& with_name) const
{
    return try_get_child(with_name).has_value();
}

std::vector<std::string> Node::children_names() const
{
    std::vector<std::string> names;
    names.reserve(m_children.size());

    for (const auto& child_node : m_children)
        names.push_back(child_node->get_name());

    return names;
}

void Node::update_hierarchical_ancestor_values(AncestorValues& ancestor_values) const
{
    int num_children = 0;
    if (!is_root())
        num_children = static_cast<int>(parent()->m_children.size());

    ancestor_values.update(FloatValue("children", "n", num_children, false));
    ancestor_values.update(FloatValue("equal", "eq", num_children > 0 ? 100.0f / static_cast<float>(num_children) : 0.0f, false));
}

void Node::insert_rendered_bounds_from_children()
{
    auto bounds = Bounds();
    for (const auto& path_and_geometry : render_tree()->children_of(path()))
        bounds += path_and_geometry.second.positioned_bounds();

    auto base_pos = bounds.base();
    render_tree()->update(path(), Geometry::empty(base_pos, bounds.strip_pos()));
}

void Node::render(AncestorValues& ancestor_values)
{
    update_hierarchical_ancestor_values(ancestor_values);
    m_element->update_ancestor_values(ancestor_values);

    for (const auto& child_node : m_children) {
        // Copy here to make sure changes in children nodes don't
        // propogate to other children
        AncestorValues new_ancestor_values = ancestor_values;
        child_node->render(new_ancestor_values);
    }

    assert(std::all_of(m_children.begin(), m_children.end(), [&](const auto& child_node) { return child_node->render_tree().get() == render_tree().get(); }));
    m_element->render(path(), render_tree());

    // It's not necessary for every element to manually add a geometry of
    // itself, but we should at least have some geometry for it in the
    // tree so parent elements correctly get the bounds of that child when
    // asking
    if (!render_tree()->get(path()).has_value())
        insert_rendered_bounds_from_children();
}

void RootNode::render_from_root()
{
    AncestorValues ancestor_values;
    Node::render(ancestor_values);
}

}
