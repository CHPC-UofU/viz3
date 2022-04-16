# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
import argparse
import abc

from .. import core


class AbstractRenderer(abc.ABC):
    """
    Base class for a 3D renderer.

    See panda3d.py and web.py for an example.
    """

    def __init__(self, layout_engine: core.LayoutEngine):
        self._layout_engine = layout_engine

    def request_listener(self) -> core.EventListener:
        """
        Returns a Listener that returns new events when available.
        """
        return self._layout_engine.request_listener()

    @abc.abstractmethod
    def run(self):
        """
        Runs the renderer on the current thread (probably on the main thread,
        since Panda3D doesn't like to be anywhere else).
        """
        raise NotImplementedError()


def add_renderer_args(parser: argparse.ArgumentParser):
    """
    Configures an argparse ArgumentParser with options to pick a default
    builtin renderer (e.g. web or panda3d).

    Use from_args() to return a AbstractRenderer from the parsed args.
    """
    renderer_group = parser.add_mutually_exclusive_group()
    renderer_group.add_argument(
        "--web", "-w",
        dest="web_port",
        type=int,
        nargs="?",
        const=8493,
        help="Whether to run a webserver renderer on the given port or 8493 (V-I-Z-3 on a phone dial)"
    )
    renderer_group.add_argument(
        "--panda3d",
        action="store_true",
        default=True,
        help="Whether to run a Panda3D GUI renderer"
    )


def from_args(args: argparse.Namespace, layout_engine: core.LayoutEngine) -> AbstractRenderer:
    """
    Returns an AbstractRenderer from the arguments configured with
    add_renderer_args().

    Raises ValueError if no args were matched against.
    """
    if args.web_port:
        from . import web
        return web.WebRenderer(layout_engine, port=args.web_port)
    if args.panda3d:
        from . import panda3d
        return panda3d.Panda3dRenderer(layout_engine)
    raise ValueError("No argparse args given that specify a renderer (did you "
                     "call add_renderer_args?)")
