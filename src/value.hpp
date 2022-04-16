// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once

#include <iostream>
#include <cassert>
#include <exception>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <map>
#include <unordered_set>
#include <utility>
#include <sstream>
#include <vector>
#include <variant>

#include "value_types.hpp"
#include "color.hpp"
#include "rotation.hpp"

namespace viz3 {

class AncestorValues;

class AbstractValue {
public:
    AbstractValue(std::string name, std::string abbreviation)
        : m_value_name(std::move(name))
        , m_abbreviation(std::move(abbreviation)) {};
    virtual ~AbstractValue() = default;
    AbstractValue(const AbstractValue&) = default;

    [[nodiscard]] std::string name() const { return m_value_name; }
    [[nodiscard]] std::string abbreviation() const { return m_abbreviation; }

    [[nodiscard]] virtual bool is_relative() const = 0;
    [[nodiscard]] virtual std::string relative_name() const = 0;
    virtual void update_ancestor_values(AncestorValues&) = 0;

    [[nodiscard]] virtual bool matches_attribute_name(const std::string_view&) const;
    [[nodiscard]] virtual std::string string() const = 0;

private:
    std::string m_value_name;
    std::string m_abbreviation;
};

class FloatValue;
class UnitIntervalValue;
class IntValue;
class BoolValue;
class StringValue;
class ColorValue;
class RotationValue;

template <typename Type, class DerivedValue>
class TypedValue : public AbstractValue {
public:
    TypedValue(const std::string& name, const std::string& abbreviation, Type value, bool is_default)
        : AbstractValue(name, abbreviation)
        , m_value(value)
        , m_defaulted(is_default) {};
    TypedValue(const TypedValue&) = default;

    [[nodiscard]] bool is_relative() const override { return false; };
    [[nodiscard]] std::string relative_name() const override { assert(false); return ""; };

    void set_value(Type value) { update_computed_value(value); set_undefaulted(); }
    [[nodiscard]] Type value() const
    {
        return m_value;
    }

    [[nodiscard]] bool is_defaulted() const { return m_defaulted; };

    [[nodiscard]] std::string string() const override
    {
        std::stringstream ss;
        ss << value();
        return ss.str();
    }

protected:
    void set_undefaulted() { m_defaulted = false; }
    void update_computed_value(Type value) { m_value = value; }

private:
    Type m_value;
    bool m_defaulted;
};

class BoolValue : public TypedValue<bool, BoolValue> {
public:
    using TypedValue::TypedValue;

    void update_ancestor_values(AncestorValues& ancestor_values) override;
};

class IntValue : public TypedValue<int, IntValue> {
public:
    using TypedValue::TypedValue;

    void update_ancestor_values(AncestorValues& ancestor_values) override;
};

class FloatValue : public TypedValue<float, FloatValue> {
public:
    using TypedValue::TypedValue;

    void update_ancestor_values(AncestorValues& ancestor_values) override;
};

class UnitIntervalValue : public TypedValue<UnitInterval, UnitIntervalValue> {
public:
    using TypedValue::TypedValue;

    void update_ancestor_values(AncestorValues& ancestor_values) override;
};

class StringValue : public TypedValue<std::string, StringValue> {
public:
    using TypedValue::TypedValue;

    void update_ancestor_values(AncestorValues& ancestor_values) override;
};

class ColorValue : public TypedValue<color::RGBA, ColorValue> {
public:
    using TypedValue::TypedValue;

    void update_ancestor_values(AncestorValues& ancestor_values) override;
};

class RotationValue : public TypedValue<Rotation, RotationValue> {
public:
    using TypedValue::TypedValue;

    void update_ancestor_values(AncestorValues& ancestor_values) override;
};

class AxisValue : public TypedValue<Axis, AxisValue> {
public:
    using TypedValue::TypedValue;

    void update_ancestor_values(AncestorValues& ancestor_values) override;
};

class AlignmentValue : public TypedValue<Alignment, AlignmentValue> {
public:
    using TypedValue::TypedValue;

    void update_ancestor_values(AncestorValues& ancestor_values) override;
};

[[nodiscard]] std::vector<std::string> topological_sort_with_aliases(const std::map<std::string, std::optional<std::string>>& dependencies,
                                                                     const std::map<std::string, std::string>& aliases);

// Note: method implementations are in corresponding .cpp file; any users of
//       this template must add an explicit instantiation at the end of the cpp
//       file for things to work!
template <typename FloatType>
class RelativeFloatTypeValue : public FloatValue {
public:
    RelativeFloatTypeValue(const std::string& name, const std::string& abbreviation, const std::string& relative_name,
                           FloatType default_value, FloatType multiplier, bool is_percentage, bool is_default)
        // is_default: false -> all relative values are non-default
        : FloatValue(name, abbreviation, default_value, is_default)
        , m_multiplier(multiplier)
        , m_is_percentage(is_percentage)
        , m_relative_name(relative_name) {};
    RelativeFloatTypeValue(const std::string& name, const std::string& abbreviation, FloatType value,
                           FloatType multiplier, bool is_percentage, bool is_default)
        : FloatValue(name, abbreviation, value, is_default)
        , m_multiplier(multiplier)
        , m_is_percentage(is_percentage)
        , m_relative_name({}) {};
    RelativeFloatTypeValue(const std::string& name, const std::string& abbreviation, FloatType value, bool is_default)
        : FloatValue(name, abbreviation, value, is_default)
        , m_multiplier(1.0)
        , m_is_percentage(false)
        , m_relative_name({}) {};
    RelativeFloatTypeValue(const RelativeFloatTypeValue&) = default;

    void update_from_attribute_value(const std::string&);
    void update_ancestor_values(AncestorValues& ancestor_values) override;

    void set_value(FloatType value);

    void set_relative_name(const std::string& relative_name) { m_relative_name = relative_name; }
    [[nodiscard]] std::string relative_name() const override
    {
        assert(is_relative());
        return m_relative_name.value();
    }

    [[nodiscard]] bool is_relative() const override { return m_relative_name.has_value(); }
    [[nodiscard]] std::string string() const override;

private:
    FloatType compute_relative_value(const AncestorValues& known_values) const;

    float m_multiplier;
    bool m_is_percentage;
    std::optional<std::string> m_relative_name;
};

using RelativeFloatValue = RelativeFloatTypeValue<float>;

class AncestorValues {
public:
    AncestorValues()
        : m_ancestor_values() {};

    void update(const FloatValue& value) { update_impl<FloatValue>(value); }
    void update(const UnitIntervalValue& value) { update_impl<UnitIntervalValue>(value); }
    void update(const BoolValue& value) { update_impl<BoolValue>(value); }
    void update(const IntValue& value) { update_impl<IntValue>(value); }
    void update(const StringValue& value) { update_impl<StringValue>(value); }
    void update(const ColorValue& value) { update_impl<ColorValue>(value); }
    void update(const RotationValue& value) { update_impl<RotationValue>(value); }
    void update(const AxisValue& value) { update_impl<AxisValue>(value); }
    void update(const AlignmentValue& value) { update_impl<AlignmentValue>(value); }
    [[nodiscard]] auto get_float(const std::string& name) const { return get<float, ValueType::Float, FloatValue>(name); }
    [[nodiscard]] auto get_unit_interval(const std::string& name) const { return get<float, ValueType::UnitInterval, UnitIntervalValue>(name); }
    [[nodiscard]] auto get_bool(const std::string& name) const { return get<bool, ValueType::Bool, BoolValue>(name); }
    [[nodiscard]] auto get_int(const std::string& name) const { return get<int, ValueType::Int, IntValue>(name); }
    [[nodiscard]] auto get_string(const std::string& name) const { return get<std::string, ValueType::String, StringValue>(name); }
    [[nodiscard]] auto get_color(const std::string& name) const { return get<color::RGBA, ValueType::Color, ColorValue>(name); }
    [[nodiscard]] auto get_rotation(const std::string& name) const { return get<Rotation, ValueType::Rotation, RotationValue>(name); }
    [[nodiscard]] auto get_axis(const std::string& name) const { return get<Axis, ValueType::Axis, AxisValue>(name); }
    [[nodiscard]] auto get_alignment(const std::string& name) const { return get<Alignment, ValueType::Alignment, AlignmentValue>(name); }

private:
    enum class ValueType {
        Float,
        UnitInterval,
        Bool,
        Int,
        String,
        Color,
        Rotation,
        Axis,
        Alignment,
    };
    static const char* value_type_string(ValueType value_type);

    template <class Value>
    void update_impl(const Value& value)
    {
        assert(!value.is_defaulted());
        auto name = value.name();
        m_ancestor_values.insert_or_assign(name, value);
    }

    template <typename Type, ValueType value_type, typename Value>
    [[nodiscard]] Type get(const std::string& name) const
    {
        for (const auto& [value_name, value_variant] : m_ancestor_values) {
            if (!std::holds_alternative<Value>(value_variant))
                continue;

            const auto& value_wrapper = std::get<Value>(value_variant);
            if (value_wrapper.name() == name || value_wrapper.abbreviation() == name)
                return value_wrapper.value();
        }

        std::string error = "Requested relative value ";
        error += name;
        error += " of type ";
        error += value_type_string(value_type);
        error += " could not be found in ancestor values (missing ancestor or incompatible type)!";
        throw std::runtime_error(error);
    }

    std::map<std::string, std::variant<FloatValue, UnitIntervalValue, BoolValue, IntValue, StringValue, ColorValue, RotationValue, AxisValue, AlignmentValue>> m_ancestor_values;
};

}
