// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <algorithm>
#include <ostream>
#include <string>
#include <regex>
#include <iostream>

#include "path.hpp"

namespace viz3 {

static const char* valid_path_part_pattern = "^[a-zA-Z0-9:_-]+$";
static const std::regex valid_path_part_regex(valid_path_part_pattern);

bool is_valid_path_part(const std::string& part)
{
    return std::regex_match(part, valid_path_part_regex);
}

static std::string throw_invalid_part_exception(const std::string& part)
{
    auto explaination = std::string("Part given in path is not a valid path part: '");
    explaination += part;
    explaination += "'. A valid part must match: ";
    explaination += valid_path_part_pattern;
    throw std::invalid_argument(explaination);
}

Path::Path(const std::string& dot_string)
{
    if (dot_string.empty() || dot_string == ".")
        return;

    std::vector<std::string> parts;
    size_t pos = 0, prev_pos = dot_string[0] == '.' ? 1 : 0;
    while ((pos = dot_string.find('.', prev_pos)) != std::string::npos) {
        auto part = dot_string.substr(prev_pos, pos - prev_pos);
        if (part.empty())
            throw std::invalid_argument("Path given has '..' within it: " + dot_string);
        else if (!is_valid_path_part(part))
            throw_invalid_part_exception(part);

        parts.emplace_back(part);
        prev_pos = pos + 1;  // skip '.'
    }

    auto part = dot_string.substr(prev_pos);
    if (!is_valid_path_part(part))
        throw_invalid_part_exception(part);

    parts.emplace_back(part);
    m_parts = move(parts);
}

Path Path::without_first() const
{
    if (empty())
        return {};

    std::vector<std::string> new_parts {};
    new_parts.reserve(size() - 1);
    std::copy(m_parts.begin() + 1, m_parts.end(), std::back_inserter(new_parts));
    return new_parts;
}

Path Path::without_last() const
{
    if (empty())
        return {};

    std::vector<std::string> new_parts {};
    new_parts.reserve(size() - 1);
    std::copy(m_parts.begin(), m_parts.end() - 1, std::back_inserter(new_parts));
    return new_parts;
}

Path Path::without_common_ancestor(const Path& other) const {
    std::vector<std::string> new_parts {};
    std::copy(after_common_ancestor(other), m_parts.end(), std::back_inserter(new_parts));
    return new_parts;
}

bool Path::is_leaf() const
{
    return size() <= 1;
}

bool Path::is_child_of(const Path& other) const
{
    return size() == other.size() + 1 && is_descendant_of(other);
}

bool Path::is_descendant_of(const Path& other, bool or_are_same) const
{
    size_t candidate_size = other.size();
    size_t our_size = size();
    if (candidate_size > our_size)
        return false;
    if (!or_are_same && candidate_size == our_size)
        return false;

    return std::equal(other.m_parts.begin(), other.m_parts.end(), m_parts.begin());
}

bool Path::is_descendant_of(const Path& path) const
{
    return is_descendant_of(path, false);
}

std::vector<Path> Path::paths_between(const Path& path, bool including_self) const
{
    std::vector<Path> intermediate_paths {};
    Path curr_path = *this;
    if (including_self)
        intermediate_paths.emplace_back(curr_path);

    if (empty())
        return intermediate_paths;

    curr_path = curr_path.without_last();
    while (!path.is_descendant_of(curr_path, true)) {
        intermediate_paths.emplace_back(curr_path);
        curr_path = curr_path.without_last();
    }
    return intermediate_paths;
}

std::vector<Path> Path::ancestor_paths(bool including_self) const
{
    std::vector<Path> paths {};
    Path curr_path = *this;
    if (including_self)
        paths.emplace_back(curr_path);

    curr_path = curr_path.without_last();
    while (!curr_path.empty()) {
        paths.emplace_back(curr_path);
        curr_path = curr_path.without_last();
    }

    return paths;
}

Path Path::join_after_common_descendant(const Path& other) const
{
    std::vector<std::string> new_parts {};
    std::copy(m_parts.begin(), common_descendant(other), std::back_inserter(new_parts));
    std::copy(other.m_parts.begin(), other.m_parts.end(), std::back_inserter(new_parts));
    return new_parts;
}

Path Path::common_ancestor_with(const Path& other) const
{
    std::vector<std::string> new_parts {};
    std::copy(m_parts.begin(), after_common_ancestor(other), std::back_inserter(new_parts));
    return new_parts;
}

Path Path::child_of_common_ancestor_with(const Path& other) const
{
    auto common_part_it = after_common_ancestor(other);
    if (common_part_it != m_parts.end())
        ++common_part_it;

    std::vector<std::string> new_parts {};
    std::copy(m_parts.begin(), common_part_it, std::back_inserter(new_parts));
    return new_parts;
}

int Path::comparison(const Path& other) const
{
    auto our_size = size();
    auto other_size = other.size();
    if (our_size > other_size)
        return 1;
    if (our_size < other_size)
        return -1;

    for (size_t i = 0; i < our_size; i++) {
        if (m_parts.at(i) > other.m_parts.at(i))
            return 1;
        if (m_parts.at(i) < other.m_parts.at(i))
            return -1;
    }
    return 0;
}

std::vector<std::string>::const_iterator Path::after_common_ancestor(const Path& other) const
{
    auto [mismatch_it, _] = std::mismatch(m_parts.begin(), m_parts.end(), other.m_parts.begin(), other.m_parts.end());
    return mismatch_it;
}

std::vector<std::string>::const_iterator Path::common_descendant(const Path& other) const
{
    if (other.empty())
        return m_parts.begin();

    return std::find(m_parts.begin(), m_parts.end(), other.first());
}

std::ostream& operator<<(std::ostream& os, const Path& path)
{
    if (path.empty()) {
        os << ".";
        return os;
    }

    for (const auto& part : path.m_parts)
        os << "." << part;
    return os;
}

}
