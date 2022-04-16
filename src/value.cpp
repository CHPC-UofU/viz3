// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <locale>
#include <iostream>

#include <boost/bimap.hpp>
#include <boost/graph/adjacency_list.hpp>
#include <boost/graph/topological_sort.hpp>

#include "value.hpp"
#include "value_types.hpp"

namespace viz3 {

const char* AncestorValues::value_type_string(ValueType value_type)
{
    switch (value_type) {
    case ValueType::Float:
        return "float";
    case ValueType::UnitInterval:
        return "unit_interval";
    case ValueType::Bool:
        return "bool";
    case ValueType::Int:
        return "int";
    case ValueType::String:
        return "string";
    case ValueType::Color:
        return "color";
    case ValueType::Rotation:
        return "rotation";
    case ValueType::Axis:
        return "axis";
    case ValueType::Alignment:
        return "alignment";
    }

    assert(false);
    return "";
}

bool AbstractValue::matches_attribute_name(const std::string_view& attribute) const
{
    return attribute == name() || attribute == abbreviation();
}

void FloatValue::update_ancestor_values(AncestorValues& ancestor_values)
{
    if (!is_defaulted())
        ancestor_values.update(*this);
}

void UnitIntervalValue::update_ancestor_values(AncestorValues& ancestor_values)
{
    if (!is_defaulted())
        ancestor_values.update(*this);
}

void BoolValue::update_ancestor_values(AncestorValues& ancestor_values)
{
    if (!is_defaulted())
        ancestor_values.update(*this);
}

void IntValue::update_ancestor_values(AncestorValues& ancestor_values)
{
    if (!is_defaulted())
        ancestor_values.update(*this);
}

void StringValue::update_ancestor_values(AncestorValues& ancestor_values)
{
    if (!is_defaulted())
        ancestor_values.update(*this);
}

void ColorValue::update_ancestor_values(AncestorValues& ancestor_values)
{
    if (!is_defaulted())
        ancestor_values.update(*this);
}

void RotationValue::update_ancestor_values(AncestorValues& ancestor_values)
{
    if (!is_defaulted())
        ancestor_values.update(*this);
}

void AxisValue::update_ancestor_values(AncestorValues& ancestor_values)
{
    if (!is_defaulted())
        ancestor_values.update(*this);
}

void AlignmentValue::update_ancestor_values(AncestorValues& ancestor_values)
{
    if (!is_defaulted())
        ancestor_values.update(*this);
}

template <typename FloatType>
FloatType RelativeFloatTypeValue<FloatType>::compute_relative_value(const AncestorValues& known_values) const
{
    float val = 0.0;
    if (!is_relative())
        val = m_is_percentage ? m_multiplier : value() * m_multiplier;
    else
        val = known_values.get_float(relative_name()) * m_multiplier;

    if (m_is_percentage) {
        auto ancestor_value = known_values.get_float(name());
        val = ancestor_value * (val / 100.0f);  // e.g. 90% -> means 90% of ancestor
    }

    return val;
}

template <typename FloatType>
void RelativeFloatTypeValue<FloatType>::update_ancestor_values(AncestorValues& ancestor_values)
{
    // FIXME: I'm not a fan of side effects like these
    auto computed_value = compute_relative_value(ancestor_values);
    update_computed_value(computed_value);

    if (is_defaulted())
        return;

    auto non_relative_float_value = FloatValue(name(), abbreviation(), computed_value, false);
    ancestor_values.update(non_relative_float_value);
}

template <typename FloatType>
void RelativeFloatTypeValue<FloatType>::set_value(FloatType value)
{
    FloatValue::set_value(value);
    m_is_percentage = false;
    m_multiplier = 1.0;
}

static std::string parse_relative_name(const std::string& attribute_value, size_t start_index, size_t from_end_index)
{
    std::string_view attribute_view = attribute_value;
    attribute_view.remove_prefix(start_index);
    attribute_view.remove_suffix(from_end_index);

    return std::string(attribute_view);
}

static std::pair<size_t, float> parse_multiplier(const std::string& attribute_value)
{
    size_t next_index = 0;
    float multiplier = std::stof(attribute_value, &next_index);
    return { next_index, multiplier };
}

template <typename FloatType>
void RelativeFloatTypeValue<FloatType>::update_from_attribute_value(const std::string& attribute_value)
{
    if(attribute_value.empty())
        return;

    // All or nothing; set these initially before finally writing out if no error so
    // if error is caught state is rolled back
    bool is_percentage = false;
    float multiplier = 1.0;
    std::optional<float> maybe_value;

    size_t attribute_value_size = attribute_value.size();
    size_t from_end_index = 0;
    size_t next_index = 0;

    if (attribute_value[attribute_value_size - 1] == '%') {
        if (attribute_value_size == 1) {
            std::string error = "Percentage given without amount: ";
            error += attribute_value;
            throw std::runtime_error(error);
        }

        is_percentage = true;
        from_end_index = 1;
    }

    if (std::isdigit(attribute_value[0]) || attribute_value[0] == '+' || attribute_value[0] == '-') {
        auto next_index_and_multiplier = parse_multiplier(attribute_value);
        next_index = next_index_and_multiplier.first;
        multiplier = next_index_and_multiplier.second;
    }

    if (next_index + from_end_index < attribute_value_size) {
        auto relative = parse_relative_name(attribute_value, next_index, from_end_index);
        set_relative_name(relative);
    }
    else if (!is_percentage) {
        maybe_value = multiplier;
        multiplier = m_multiplier;
    }

    m_is_percentage = is_percentage;
    m_multiplier = multiplier;
    set_undefaulted();
    if (maybe_value) set_value(*maybe_value);
}

template <typename FloatType>
std::string RelativeFloatTypeValue<FloatType>::string() const
{
    if (!is_relative())
        return std::to_string(value());

    std::string as_str;
    if (m_multiplier != 1.0)
        as_str += std::to_string(m_multiplier);

    as_str += relative_name();
    return as_str;
}

std::string resolve_alias(const std::string& name, const std::map<std::string, std::string>& aliases)
{
    auto resolved_name = name;

    auto aliases_it = aliases.find(resolved_name);
    if (aliases_it != aliases.end())
        resolved_name = aliases_it->second;

    return resolved_name;
}

std::vector<std::string> topological_sort_with_aliases(const std::map<std::string, std::optional<std::string>>& dependencies,
                                                       const std::map<std::string, std::string>& aliases)
{
    // FIXME: This is frankly pretty messy and not the most efficient thing...
    //        Maybe we should just write our own topological sort?
    boost::adjacency_list<boost::listS, boost::vecS, boost::directedS, int> graph;
    boost::bimap<int, std::string> indexes;

    // First map strings to indexes while also resolving aliases; this is so
    // we avoid copying strings everywhere
    int i = 0;
    for (const auto& [name, maybe_dep] : dependencies) {
        std::optional<std::string> resolved_dep;
        if (maybe_dep.has_value())
            resolved_dep = resolve_alias(*maybe_dep, aliases);

        int name_index = -1;
        auto indexes_it = indexes.right.find(name);
        if (indexes_it == indexes.right.end()) {
            name_index = i;
            indexes.insert({name_index, name});
            boost::add_vertex(name_index, graph);
            i++;
        }
        else {
            name_index = indexes_it->get_left();
        }

        if (resolved_dep.has_value()) {
            auto dep = *resolved_dep;
            int dep_index = -1;

            indexes_it = indexes.right.find(dep);
            if (indexes_it == indexes.right.end()) {
                dep_index = i;
                indexes.insert({dep_index, dep});
                boost::add_vertex(dep_index, graph);
                i++;
            }
            else {
                dep_index = indexes_it->get_left();
            }
            boost::add_edge(dep_index, name_index, graph);
        }
    }

    std::deque<int> order;
    try {
        boost::topological_sort(graph, std::front_inserter(order));
    }
    catch (const boost::not_a_dag&) {
        std::string error = "Attributes given form a cycle: ";
        for (const auto& [name, maybe_dep] : dependencies) {
            error += "{ " + name;
            if (maybe_dep.has_value())
                error += " -> " + *maybe_dep;
            error += " } ";
        }
        throw std::runtime_error(error);
    }

    std::vector<std::string> new_ordered_names;
    new_ordered_names.reserve(dependencies.size());
    for (const auto index : order) {
        auto indexes_it = indexes.left.find(index);
        assert(indexes_it != indexes.left.end());

        auto name = indexes_it->second;
        auto values_it = dependencies.find(name);
        if (values_it == dependencies.end())
            continue;

        new_ordered_names.push_back(values_it->first);
    }

    return new_ordered_names;
}

// Explicit instantiation required for template implementation, otherwise linking issues
template class RelativeFloatTypeValue<float>;
template class RelativeFloatTypeValue<UnitInterval>;

}
