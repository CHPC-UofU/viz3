#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
import argparse
import os
import sys
import threading
import time

import viz3.core
import viz3.colors
import viz3.datagraph
import viz3.visualize
import viz3.renderer
import viz3.utils


def update_loop(viz, constraints, num_updates):
    while num_updates > 0:
        num_updates -= 1
        viz.update(constraints)
        time.sleep(10)


def parse_args():
    parser = argparse.ArgumentParser()
    viz3.renderer.add_renderer_args(parser)
    parser.add_argument("yaml_file", help="Path to YAML file that defines the datasources")
    parser.add_argument("xml_file", help="Path to XML file that defines the visualization")
    parser.add_argument("constraints", nargs="*", help="Data graph name=value constraints such as redfish:instance=cluster100")
    parser.add_argument(
        "-n", "--num-updates",
        type=int,
        default=99999999,
        help="Number of times to update."
    )

    args = parser.parse_args()
    if not os.path.isfile(args.xml_file):
        print("XML file given does not exist: " + args.xml_file, file=sys.stderr)
        sys.exit(2)

    return args


def convert_room_temp_to_color(temp_fixpt_c, color_range_ctor=viz3.colors.OrangeRedColorRange):
    temp_c = temp_fixpt_c / 10
    if temp_c < 20.0:
        return [viz3.core.RGBA.from_string("gray1", 0.2)]

    color_range = color_range_ctor(20, 30, 0.5)
    return [color_range.rgb_color(temp_c)]


def convert_power_to_color(power_watts, color_range_ctor=viz3.colors.RedBlueColorRange):
    if power_watts < 50.0:
        return [viz3.core.RGBA.from_string("gray1", 0.2)]

    color_range = color_range_ctor(5_000, 15_000, opacity=0.5)
    return [color_range.rgb_color(power_watts)]


def convert_humidity_to_opacity(humidity_pct):
    return [min((humidity_pct + 60) / 100, 1.0)]


def convert_lm_temp_to_color(lm_temp, color_range_ctor=viz3.colors.OrangeRedColorRange):
    if lm_temp < 20_000:
        return [viz3.core.RGBA.from_string("gray1", 0.2)]

    color_range = color_range_ctor(20_000, 80_000, opacity=0.5)
    return [color_range.rgb_color(lm_temp)]


def convert_temp_to_color(temp_c, color_range_ctor=viz3.colors.OrangeRedColorRange):
    if temp_c < 15.0:
        return [viz3.core.RGBA.from_string("gray1", 0.2)]

    color_range = color_range_ctor(15, 30, 0.5)
    return [color_range.rgb_color(temp_c)]


def convert_pdu_temp_to_color(temp_fix_pt):
    return convert_temp_to_color(temp_fix_pt / 10)


def convert_cpu_temp_to_color(temp_c, color_range_ctor=viz3.colors.OrangeRedColorRange):
    if temp_c < 15.0:
        return [viz3.core.RGBA.from_string("gray1", 0.2)]

    color_range = color_range_ctor(15, 85, 0.5)
    return [color_range.rgb_color(temp_c)]


def convert_fanspeed_to_color(fanspeed_pct):
    if fanspeed_pct >= 100 or not math.isfinite(fanspeed_pct):
        fanspeed_pct = 0.0
    return [viz3.colors.BluePurpleColorRange(0, 100).rgb_color(fanspeed_pct)]


def convert_pct_to_color(pct):
    return [viz3.colors.BluePurpleColorRange(0, 100).rgb_color(pct)]


def green_red_color(pct):
    return [viz3.colors.GreenRedColorRange(0, 100).rgb_color(pct)]


def health_color(state):
    if state == 1:
        return [viz3.core.RGBA.from_string("gray4")]
    elif state == 2:
        return [viz3.core.RGBA.from_string("orange2")]
    return [viz3.core.RGBA.from_string("red5")]


def green_health_color(state):
    if state == 1:
        return [viz3.core.RGBA.from_string("green4")]
    elif state == 2:
        return [viz3.core.RGBA.from_string("orange2")]
    return [viz3.core.RGBA.from_string("red5")]


def state_to_opacity(state):
    return [min(max(0.5 + state, 1.0), 0.0)]


def green_red_dark_color(pct):
    return [viz3.colors.GreenRedDarkColorRange(0, 100).rgb_color(pct)]


def main(args):
    viz = viz3.visualize.DynamicVisualization.from_xml(args.yaml_file, args.xml_file)
    viz.add_transformation("power_to_color", convert_power_to_color)
    viz.add_transformation("room_temp_to_color", convert_room_temp_to_color)
    viz.add_transformation("humidity_to_opacity", convert_humidity_to_opacity)
    viz.add_transformation("lm_temp_to_color", convert_lm_temp_to_color)
    viz.add_transformation("temp_to_color", convert_temp_to_color)
    viz.add_transformation("pct_to_color", convert_pct_to_color)
    viz.add_transformation("cpu_temp_to_color", convert_cpu_temp_to_color)
    viz.add_transformation("gpu_temp_to_color", convert_cpu_temp_to_color)
    viz.add_transformation("fanspeed_to_color", convert_fanspeed_to_color)
    viz.add_transformation("green_red_color", green_red_color)
    viz.add_transformation("green_red_dark_color", green_red_dark_color)
    viz.add_transformation("health_color", health_color)
    viz.add_transformation("green_health_color", green_health_color)
    viz.add_transformation("state_to_opacity", state_to_opacity)

    constraints = {}
    for constraint in args.constraints:
        mangled_name, expected_value = constraint.split("=", maxsplit=1)
        constraints[mangled_name] = expected_value

    thread = threading.Thread(target=update_loop, args=(viz, constraints, args.num_updates))
    thread.start()

    renderer = viz3.renderer.from_args(args, viz.layout_engine())
    renderer.run()


if __name__ == "__main__":
    args = parse_args()
    main(args)
