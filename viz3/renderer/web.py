# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Defines a bunch of utilities for setting up a SSE webserver renderer.
"""
import json
import logging
import os
import pkg_resources
import time

import flask

from .. import core
from .. import renderer

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class EventJSONEncoder(json.JSONEncoder):
    """
    Encodes viz3 objects to JSON.

    Usage: EventJSONEncoder().encode(...)
    """

    def default(self, obj):
        if isinstance(obj, core.Event):
            return {
                "path": self.default(obj.path),
                "geometry": self.default(obj.geometry),
                "event_type": self.default(obj.type),
            }
        elif isinstance(obj, core.Path):
            return str(obj)
        elif isinstance(obj, core.Point):
            return {
                "x": obj.x,
                "y": obj.y,
                "z": obj.z,
            }
        elif isinstance(obj, core.RGBA):
            return {
                "r": obj.r,
                "g": obj.g,
                "b": obj.b,
                "a": obj.a
            }
        elif isinstance(obj, core.Geometry):
            # We map objects to self.default if and only if there is no
            # corresponding representation in JSON (except for float, since
            # we need to map inf to a special value).
            # e.g. self.default(return_bool()) is not allowed. In fact, it will
            #      cause an exception to be raised
            return {
                "vertexes": list(map(self.default, obj.vertexes())),
                "triangles": obj.triangles(),
                "bounds": self.default(obj.bounds()),
                "pos": self.default(obj.pos),
                "color": self.default(obj.color),
                "hide_distance": self.default(obj.hide_distance),
                "show_distance": self.default(obj.show_distance),
                "should_draw": obj.should_draw(),
                "text": obj.text,
            }
        elif isinstance(obj, core.Bounds):
            return {
                "base": self.default(obj.base()),
                "end": self.default(obj.end()),
            }
        elif isinstance(obj, core.EventType):
            return int(obj)
        elif isinstance(obj, float):
            # FLT_MAX in float.h (assuming 32-bit floats); infinity is not
            # representible in JSON
            return obj if obj != float("inf") else 3.40282347e+38
        return super().default(obj)


static_dir = pkg_resources.resource_filename("viz3", "static/")


class WebRenderer(renderer.AbstractRenderer):

    def __init__(self, layout_engine: core.LayoutEngine, host: str = "0.0.0.0", port: int = 8493):
        """
        Creates a renderer that streams events to the web. By default, runs on
        0.0.0.0:8493 (8493 is viz3 on phone dial).

        I wouldn't necessarily trust the web server to be completely safe; this
        is experimental, though it is just a straightforward flask server.
        """
        super().__init__(layout_engine)
        self._host = host
        self._port = port
        self._app = flask.Flask(__name__)

        @self._app.route("/events")
        def events():
            def stream_events():
                listener = self.request_listener()
                while True:
                    # For some reason listen() causes problems with locking
                    maybe_event = listener.listen()
                    if not maybe_event:
                        return

                    json_data = EventJSONEncoder().encode(maybe_event)
                    yield "data:{}\n\n".format(json_data)

            return flask.Response(stream_events(), mimetype="text/event-stream")

        @self._app.route("/")
        def index():
            return flask.send_from_directory(static_dir, "index.html")

        @self._app.route("/<path:path>")
        def javascript(path):
            filename = os.path.basename(path)
            return flask.send_from_directory(static_dir, filename)

    def run(self):
        logger.warning("Running webserver on %s:%s", self._host, self._port)
        self._app.run(host=self._host, port=self._port)
        while True:
            time.sleep(0.5)
