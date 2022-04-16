// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <initializer_list>
#include <memory>
#include <ostream>
#include <sstream>
#include <string>
#include <vector>

namespace viz3 {

bool is_valid_path_part(const std::string& part);

/*
 * A Path describes a sequence of nodes within a tree or graph to traverse.
 */
struct Path {
    explicit Path(const std::string& dot_string);
    Path(std::vector<std::string> parts)
        : m_parts(move(parts)) {};
    Path(std::initializer_list<std::string> parts)
        : m_parts(parts) {};

    std::vector<std::string> parts() const { return m_parts; }
    std::string first() const { return empty() ? "" : m_parts.at(0); }
    std::string last() const { return empty() ? "" : m_parts.at(size() - 1); }
    Path without_first() const;
    Path without_last() const;
    Path without_common_ancestor(const Path&) const;
    bool is_child_of(const Path&) const;
    bool is_descendant_of(const Path&, bool or_are_same) const;
    bool is_descendant_of(const Path&) const;
    std::vector<Path> paths_between(const Path&, bool including_self) const;
    std::vector<Path> ancestor_paths(bool including_self) const;
    Path join_after_common_descendant(const Path&) const;
    Path common_ancestor_with(const Path&) const;
    Path child_of_common_ancestor_with(const Path&) const;
    bool is_leaf() const;
    size_t size() const { return m_parts.size(); }
    bool empty() const { return m_parts.empty(); }

    Path operator+(const std::string& part) const
    {
        auto new_parts = parts();
        new_parts.emplace_back(part);
        return { new_parts };
    }
    Path operator+(const Path& other) const
    {
        auto new_parts = parts();
        for (const auto& part : other.parts())
            new_parts.emplace_back(part);
        return { new_parts };
    }
    Path operator-(const Path& other) const
    {
        // FIXME: Figure out where the heck this is used and replace it with
        //        the more obvious function... (Python code may be using it...)
        return without_common_ancestor(other);
    }

    bool operator<(const Path& other) const
    {
        return comparison(other) < 0;
    }
    bool operator<=(const Path& other) const
    {
        return comparison(other) <= 0;
    }
    bool operator>(const Path& other) const
    {
        return comparison(other) > 0;
    }
    bool operator>=(const Path& other) const
    {
        return comparison(other) >= 0;
    }
    bool operator==(const Path& other) const
    {
        return comparison(other) == 0;
    }
    bool operator!=(const Path& other) const
    {
        return comparison(other) != 0;
    }

    friend std::ostream& operator<<(std::ostream&, const Path&);
    std::string string() const
    {
        std::stringstream stream {};
        stream << *this;
        return stream.str();
    }

private:
    // In C++20 we have the <=> operator, but we are not using C++20 yet
    int comparison(const Path& other) const;
    std::vector<std::string>::const_iterator after_common_ancestor(const Path&) const;
    std::vector<std::string>::const_iterator common_descendant(const Path&) const;

    std::vector<std::string> m_parts;
};

}

namespace std {

template <>
struct hash<viz3::Path> {
    std::size_t operator()(const viz3::Path& path) const
    {
        // See https://en.cppreference.com/w/cpp/utility/hash
        // and https://stackoverflow.com/questions/20511347/a-good-hash-function-for-a-vector
        auto path_parts = path.parts();
        std::size_t seed = path_parts.size();
        for (auto& part : path_parts)
            seed ^= std::hash<std::string> {}(part) + 0x9e3779b9 + (seed << 6) + (seed >> 2);

        return seed;
    }
};

}
