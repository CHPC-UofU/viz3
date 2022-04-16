#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
import argparse
import collections
import datetime
import threading
import time

import networkx
import psutil

import viz3.core
import viz3.colors
import viz3.renderer


class ProcessDataSource:

    def __init__(self, layout_engine, target_path=viz3.core.Path()):
        self._layout_engine = layout_engine
        self._target_path = target_path
        self._proc_color_range = viz3.colors.RedBlueColorRange(0, 100)

        tx = self._layout_engine.transaction()
        self._create_tree(tx)
        tx.render()

    def _create_tree(self, tx):
        print("creating tree")
        root = tx.node().find_descendant(self._target_path)
        users_grid = viz3.core.GridElement("users", spacing=100)
        users_node = root.construct_child(users_grid)

        user_template_element = viz3.core.GridElement("user", spacing=10)
        user_template_node = users_node.construct_template(user_template_element)

        process_template_element = viz3.core.BoxElement("pid")
        process_template_node = user_template_node.construct_template(process_template_element)

    def _update_users_tree(self, tx, usernames):
        assert isinstance(usernames, set)

        users_node = tx.node().find_descendant(self._target_path + "users")

        existing_usernames = set(users_node.children_names())
        removed_usernames = existing_usernames - usernames
        for username in removed_usernames:
            users_node.remove_child(username)

        added_usernames = usernames - existing_usernames
        for username in added_usernames:
            user_node = users_node.try_get_child_or_make_template("user", username)

    def _update_user_processes(self, tx, username, processes):
        pids = set(proc_dict["pid"] for proc_dict in processes)

        # Templated version of construct/remove children elements
        user_path = self._target_path + "users" + username
        user_node = tx.node().find_descendant(user_path)
        existing_pids = set(map(int, user_node.children_names()))

        removed_pids = existing_pids - pids
        for pid in removed_pids:
            user_node.remove_child(str(pid))

        # The order we add things in is important: we want by ctime. So one
        # cannot simply do a pids - existing_pids to get new pids because sets
        # are unordered
        for proc_info in processes:
            pid = proc_info["pid"]
            if pid in removed_pids:
                continue

            name = proc_info["name"]
            cpu = proc_info["cpu_percent"]
            mem = proc_info["memory_percent"]
            ctime = datetime.datetime.fromtimestamp(proc_info["create_time"]).isoformat()
            ncpus = psutil.cpu_count()
            proc_color = self._proc_color_range.rgb_color(cpu)

            # update
            pid_node = user_node.try_get_child_or_make_template("pid", str(pid))
            pid_element = pid_node.element
            pid_element.width = 10
            pid_element.height = int(mem * 200)
            pid_element.depth = 10
            pid_element.color = proc_color
            pid_element.text = "{} ({}, PID: {}):\nMemory: {}%\nCPU: {}% ({} virtual cores)\nCreation Time: {}".format(
                name,
                username,
                pid,
                mem,
                cpu,
                ncpus,
                ctime,
            )

    def update(self):
        print("updating")
        procs_by_ctime = self._active_processes_by_ctime()

        user_procs_by_ctime = collections.defaultdict(list)
        for proc_dict in procs_by_ctime:
            user_procs_by_ctime[proc_dict["username"]].append(proc_dict)

        tx = self._layout_engine.transaction()

        usernames = set(user_procs_by_ctime.keys())
        self._update_users_tree(tx, usernames)
        for username, processes in user_procs_by_ctime.items():
            self._update_user_processes(tx, username, processes)

        tx.render()
        print("done updating")

    def _active_processes_by_ctime(self):
        procs_by_ctime = []
        for proc in psutil.process_iter():
            proc_info = proc.as_dict(
                attrs=[
                    "pid",
                    "name",
                    "uids",
                    "username",
                    "memory_percent",
                    "cpu_percent",
                    "create_time",
                ]
            )
            # Sometimes there are processes with None values for cpu_percent;
            # ignore these, I suspect there are permission issues...
            if any(val is None for val in proc_info.values()):
                continue

            procs_by_ctime.append(proc_info)

        procs_by_ctime.sort(key=lambda proc_dict: proc_dict["create_time"])
        return procs_by_ctime


def update_loop(layout_engine):
    process_datasource = ProcessDataSource(layout_engine)
    while True:
        process_datasource.update()
        time.sleep(5)


def parse_args():
    parser = argparse.ArgumentParser()
    viz3.renderer.add_renderer_args(parser)
    return parser.parse_args()


def main(args):
    layout_engine = viz3.core.LayoutEngine()
    thread = threading.Thread(target=update_loop, args=(layout_engine,))
    thread.start()

    renderer = viz3.renderer.from_args(args, layout_engine)
    renderer.run()


if __name__ == "__main__":
    main(parse_args())
