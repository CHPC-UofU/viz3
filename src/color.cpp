// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <exception>
#include <map>
#include <optional>
#include <regex>
#include <sstream>

#include "color.hpp"

static const std::regex valid_rgba_pattern("^(RGBA)*[(]([0-9]+),[ ]*([0-9]+),[ ]*([0-9]+)(,[ ]*([0-9]+([.][0-9]+)?))?[)]$");

namespace viz3::color {

static const std::map<std::string, RGBA> color_map {
    {"gray0",	RGBA(248, 249, 250)},
    {"gray1",	RGBA(241, 243, 245)},
    {"gray2",	RGBA(233, 236, 239)},
    {"gray3",	RGBA(222, 226, 230)},
    {"gray4",	RGBA(206, 212, 218)},
    {"gray5",	RGBA(173, 181, 189)},
    {"gray6",	RGBA(134, 142, 150)},
    {"gray7",	RGBA(73, 80, 87)},
    {"gray8",	RGBA(52, 58, 64)},
    {"gray9",	RGBA(33, 37, 41)},
    {"red0",	RGBA(255, 245, 245)},
    {"red1",	RGBA(255, 227, 227)},
    {"red2",	RGBA(255, 201, 201)},
    {"red3",	RGBA(255, 168, 168)},
    {"red4",	RGBA(255, 135, 135)},
    {"red5",	RGBA(255, 107, 107)},
    {"red6",	RGBA(250, 82, 82)},
    {"red7",	RGBA(240, 62, 62)},
    {"red8",	RGBA(224, 49, 49)},
    {"red9",	RGBA(201, 42, 42)},
    {"pink0",	RGBA(255, 240, 246)},
    {"pink1",	RGBA(255, 222, 235)},
    {"pink2",	RGBA(252, 194, 215)},
    {"pink3",	RGBA(250, 162, 193)},
    {"pink4",	RGBA(247, 131, 172)},
    {"pink5",	RGBA(240, 101, 149)},
    {"pink6",	RGBA(230, 73, 128)},
    {"pink7",	RGBA(214, 51, 108)},
    {"pink8",	RGBA(194, 37, 92)},
    {"pink9",	RGBA(166, 30, 77)},
    {"grape0",	RGBA(248, 240, 252)},
    {"grape1",	RGBA(243, 217, 250)},
    {"grape2",	RGBA(238, 190, 250)},
    {"grape3",	RGBA(229, 153, 247)},
    {"grape4",	RGBA(218, 119, 242)},
    {"grape5",	RGBA(204, 93, 232)},
    {"grape6",	RGBA(190, 75, 219)},
    {"grape7",	RGBA(174, 62, 201)},
    {"grape8",	RGBA(156, 54, 181)},
    {"grape9",	RGBA(134, 46, 156)},
    {"violet0",	RGBA(243, 240, 255)},
    {"violet1",	RGBA(229, 219, 255)},
    {"violet2",	RGBA(208, 191, 255)},
    {"violet3",	RGBA(177, 151, 252)},
    {"violet4",	RGBA(151, 117, 250)},
    {"violet5",	RGBA(132, 94, 247)},
    {"violet6",	RGBA(121, 80, 242)},
    {"violet7",	RGBA(112, 72, 232)},
    {"violet8",	RGBA(103, 65, 217)},
    {"violet9",	RGBA(95, 61, 196)},
    {"indigo0",	RGBA(237, 242, 255)},
    {"indigo1",	RGBA(219, 228, 255)},
    {"indigo2",	RGBA(186, 200, 255)},
    {"indigo3",	RGBA(145, 167, 255)},
    {"indigo4",	RGBA(116, 143, 252)},
    {"indigo5",	RGBA(92, 124, 250)},
    {"indigo6",	RGBA(76, 110, 245)},
    {"indigo7",	RGBA(66, 99, 235)},
    {"indigo8",	RGBA(59, 91, 219)},
    {"indigo9",	RGBA(54, 79, 199)},
    {"blue0",	RGBA(231, 245, 255)},
    {"blue1",	RGBA(208, 235, 255)},
    {"blue2",	RGBA(165, 216, 255)},
    {"blue3",	RGBA(116, 192, 252)},
    {"blue4",	RGBA(77, 171, 247)},
    {"blue5",	RGBA(51, 154, 240)},
    {"blue6",	RGBA(34, 139, 230)},
    {"blue7",	RGBA(28, 126, 214)},
    {"blue8",	RGBA(25, 113, 194)},
    {"blue9",	RGBA(24, 100, 171)},
    {"cyan0",	RGBA(227, 250, 252)},
    {"cyan1",	RGBA(197, 246, 250)},
    {"cyan2",	RGBA(153, 233, 242)},
    {"cyan3",	RGBA(102, 217, 232)},
    {"cyan4",	RGBA(59, 201, 219)},
    {"cyan5",	RGBA(34, 184, 207)},
    {"cyan6",	RGBA(21, 170, 191)},
    {"cyan7",	RGBA(16, 152, 173)},
    {"cyan8",	RGBA(12, 133, 153)},
    {"cyan9",	RGBA(11, 114, 133)},
    {"teal0",	RGBA(230, 252, 245)},
    {"teal1",	RGBA(195, 250, 232)},
    {"teal2",	RGBA(150, 242, 215)},
    {"teal3",	RGBA(99, 230, 190)},
    {"teal4",	RGBA(56, 217, 169)},
    {"teal5",	RGBA(32, 201, 151)},
    {"teal6",	RGBA(18, 184, 134)},
    {"teal7",	RGBA(12, 166, 120)},
    {"teal8",	RGBA(9, 146, 104)},
    {"teal9",	RGBA(8, 127, 91)},
    {"green0",	RGBA(235, 251, 238)},
    {"green1",	RGBA(211, 249, 216)},
    {"green2",	RGBA(178, 242, 187)},
    {"green3",	RGBA(140, 233, 154)},
    {"green4",	RGBA(105, 219, 124)},
    {"green5",	RGBA(81, 207, 102)},
    {"green6",	RGBA(64, 192, 87)},
    {"green7",	RGBA(55, 178, 77)},
    {"green8",	RGBA(47, 158, 68)},
    {"green9",	RGBA(43, 138, 62)},
    {"lime0",	RGBA(244, 252, 227)},
    {"lime1",	RGBA(233, 250, 200)},
    {"lime2",	RGBA(216, 245, 162)},
    {"lime3",	RGBA(192, 235, 117)},
    {"lime4",	RGBA(169, 227, 75)},
    {"lime5",	RGBA(148, 216, 45)},
    {"lime6",	RGBA(130, 201, 30)},
    {"lime7",	RGBA(116, 184, 22)},
    {"lime8",	RGBA(102, 168, 15)},
    {"lime9",	RGBA(92, 148, 13)},
    {"yellow0",	RGBA(255, 249, 219)},
    {"yellow1",	RGBA(255, 243, 191)},
    {"yellow2",	RGBA(255, 236, 153)},
    {"yellow3",	RGBA(255, 224, 102)},
    {"yellow4",	RGBA(255, 212, 59)},
    {"yellow5",	RGBA(252, 196, 25)},
    {"yellow6",	RGBA(250, 176, 5)},
    {"yellow7",	RGBA(245, 159, 0)},
    {"yellow8",	RGBA(240, 140, 0)},
    {"yellow9",	RGBA(230, 119, 0)},
    {"orange0",	RGBA(255, 244, 230)},
    {"orange1",	RGBA(255, 232, 204)},
    {"orange2",	RGBA(255, 216, 168)},
    {"orange3",	RGBA(255, 192, 120)},
    {"orange4",	RGBA(255, 169, 77)},
    {"orange5",	RGBA(255, 146, 43)},
    {"orange6",	RGBA(253, 126, 20)},
    {"orange7",	RGBA(247, 103, 7)},
    {"orange8",	RGBA(232, 89, 12)},
    {"orange9",	RGBA(217, 72, 15)},
};

static std::optional<RGBA> color_from_string(const std::string& str)
{
    auto it = color_map.find(str);
    if (it != color_map.end())
        return { it->second };

    return {};
}

RGBA RGBA::from_string(std::string string, float opacity)
{
    auto maybe_color = color_from_string(string);
    if (maybe_color.has_value()) {
        auto color = maybe_color.value();
        color.set_opacity(opacity);
        return color;
    }

    std::smatch base_match;
    if (!std::regex_match(string, base_match, valid_rgba_pattern)) {
        throw std::invalid_argument(std::string("Not a valid RGBA string: ") + string);
    }

    auto r = std::stof(base_match[2]);
    auto g = std::stof(base_match[3]);
    auto b = std::stof(base_match[4]);
    if (base_match.size() > 4) {
        opacity = std::stof(base_match[6]);
        return RGBA(r, g, b, opacity);
    }

    return RGBA(r, g, b, opacity);
}

std::string RGBA::string() const
{
    std::stringstream stream {};
    stream << *this;
    return stream.str();
}

std::ostream& operator<<(std::ostream& os, const RGBA& rgba)
{
    os << "(" << (unsigned int) rgba.r << ", " << (unsigned int) rgba.g << ", " << (unsigned int) rgba.b << ", " << rgba.opacity() << ")";
    return os;
}

}
