# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
"""
Renders a LayoutEngine tree using Panda3D.
"""
import logging

# Direct is part of panda3d; it is mostly the non-3D parts of Panda3D
import direct.showbase.ShowBase
import direct.task
import panda3d.core

from .. import core
from .. import utils
from .. import renderer

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Panda3dRenderer(direct.showbase.ShowBase.ShowBase, renderer.AbstractRenderer):
    """
    3D monitoring view, primary.

    .run() runs the Renderer. Should be on main thread.
    """

    def __init__(self, layout_engine, title="3D Visualizer"):
        """
        Initialize and set up the 3D view
        """
        direct.showbase.ShowBase.ShowBase.__init__(self)
        renderer.AbstractRenderer.__init__(self, layout_engine)

        props = panda3d.core.WindowProperties()
        props.setTitle(title)
        self.win.requestProperties(props)
        self.setBackgroundColor(1, 1, 1)  # white

        # See samples/chessboard in Panda3D examples for details; Mostly copied
        # from that without thinking too much
        self._mouse_collision_picker = panda3d.core.CollisionTraverser()
        self._mouse_collision_queue = panda3d.core.CollisionHandlerQueue()
        mouse_collision_node = panda3d.core.CollisionNode("mouse_collision")
        mouse_collision_node.setFromCollideMask(mouse_collision_node.getDefaultCollideMask())
        self._mouse_collision_node_path = self.camera.attachNewNode(mouse_collision_node)
        self._last_hovered_label_node_path = None

        self._mouse_collision_ray = panda3d.core.CollisionRay()
        mouse_collision_node.addSolid(self._mouse_collision_ray)
        self._mouse_collision_picker.addCollider(self._mouse_collision_node_path, self._mouse_collision_queue)
        taskMgr.add(self._on_mouse_hover)

        self._listener = self.request_listener()
        taskMgr.add(self._poll_and_handle_events)

    def _poll_and_handle_events(self, task):
        """
        Polls the LayoutEngine for new events and updates the events that occur.

        task: direct.task.Task
            This task, represented in direct.task. Use task.time for timing
            purposes.

            See https://docs.panda3d.org/1.10/python/programming/tasks-and-events/tasks
        """
        start_time = task.time
        while True:
            server_died, maybe_event = self._listener.poll()
            if server_died:
                logger.warning("Event server died. Proceeding without updates.")
                return direct.task.Task.done

            if maybe_event:
                self._update_from_event(maybe_event)
                # if we have time to process additional events (at 60fps)
                if task.time - start_time < 0.015:
                    continue

            return direct.task.Task.cont

    def _update_from_event(self, event):
        """
        Updates the visualization with a viz3 event.

        event: core.Event
            An event from the LayoutEngine event server.
        """
        logger.warning("Processing event %s %s", event.path, event.type.name)
        if not event.geometry.should_draw():
            logger.debug("Not drawing event %s %s", event.path, event.type.name)
            return

        if event.type == core.EventType.Move:
            logger.debug("Moving from event %s", event.path)
            self._move_from_event(event)

        elif event.type == core.EventType.Add:
            logger.debug("Adding from event %s", event.path)
            self._add_from_event(event)

        elif event.type == core.EventType.Remove:
            logger.debug("Removing from event %s", event.path)
            self._remove_from_event(event)

        elif event.type == core.EventType.Resize:
            logger.debug("Resizing from event %s", event.path)
            self._resize_from_event(event)

        elif event.type == core.EventType.Recolor:
            logger.debug("Recoloring from event %s", event.path)
            self._recolor_from_event(event)

        elif event.type == core.EventType.Retext:
            logger.debug("Retexting from event %s", event.path)
            self._retext_from_event(event)

        else:
            logger.error("Found unexpected event: %s", event.type.name)

    def _name_from_path(self, path):
        """
        Returns the Panda3D name/identifier from a LayoutEngine Path.
        """
        name = str(path)
        # Because __str__ of Path starts with a dot (e.g. .foo.bar), we don't
        # have to worry about naming conflicts with our hardcoded names of helper
        # nodes here.
        assert name.startswith(".")
        return name

    def _move_from_event(self, event):
        """
        Moves the corresponding node associated with the given event.

        event: core.Event
            An event from the LayoutEngine event server.
        """
        target_node_path = self._find_node_path(event.path)
        pos = event.geometry.pos

        coord = utils.swap_yz_coords(pos)
        self._move_node_path(target_node_path, coord)

    def _add_from_event(self, event):
        """
        Adds a node to the visualization based on the given event.

        event: core.Event
            An event from the LayoutEngine event server.
        """
        name = self._name_from_path(event.path)
        target_node_path = self._node_path_from_viz3_geometry(name, event.geometry)

        target_node_path.setTransparency(True)
        target_node_path.setColor(*self._color_from_viz3_rgba(event.geometry.color))
        target_node_path.node().setIntoCollideMask(self._mouse_collision_node_path.node().getDefaultCollideMask())

    def _remove_from_event(self, event):
        """
        Removes a node from the visualization based on the given event.

        event: core.Event
            An event from the LayoutEngine event server.
        """
        target_node_path = self._find_node_path(event.path)
        target_node_path.removeNode()

    def _resize_from_event(self, event):
        """
        Resizes a node in the visualization based on the given event.

        event: core.Event
            An event from the LayoutEngine event server.
        """
        # FIXME: This is a hack because in Panda3d Geom objects are supposed
        #        to not change their physical properties; we should switch
        #        to using an Actor if things change instead (e.g. we could be
        #        lazy about it and only do it when we encouter a resize since
        #        we are already recreating a new object on each resize)
        self._remove_from_event(event)
        self._add_from_event(event)

    def _recolor_from_event(self, event):
        """
        Recolors a node in the visualization based on the given event.

        event: core.Event
            An event from the LayoutEngine event server.
        """
        target_node_path = self._find_node_path(event.path)
        color = event.geometry.color
        target_node_path.setColor(*self._color_from_viz3_rgba(color))

    def _retext_from_event(self, event):
        """
        Retexts a node in the visualization based on the given event.

        event: core.Event
            An event from the LayoutEngine event server.
        """
        path = event.path
        geometry = event.geometry

        target_node_path = self._find_node_path(event.path)
        text_node_path = self._text_label_from_parent(target_node_path)
        if not text_node_path:
            text_node_path = self._create_text_label(geometry.text, target_node_path, geometry.bounds())
        else:
            text_node_path.node().setText(geometry.text)

    def _find_node_path(self, path):
        """
        Returns the Panda3D NodePath for the given viz3 Path or an empty
        NodePath if no such path exists.

        path: core.Path
            viz3 Path to look for.
        """
        name = self._name_from_path(path)  # core geometry names are their paths
        maybe_node_path = self.render.find(name)
        if not maybe_node_path:
            return self.render.find(self._lod_name(name) + "/" + name)  # see _create_lod

        return maybe_node_path

    def _lod_name(self, parent_name):
        return parent_name + "_lod"

    def _create_lod(self, name, node_path, hide_distance, show_distance):
        """
        Creates a parent Level-Of-Detail node for the given geometry
        """
        # See https://docs.panda3d.org/1.10/python/programming/models-and-actors/level-of-detail
        lod = panda3d.core.LODNode(self._lod_name(name))
        lod_node_path = self.render.attachNewNode(lod)
        lod.addSwitch(show_distance, hide_distance)
        node_path.reparentTo(lod_node_path)
        return lod_node_path

    def _text_label_name(self, parent_name):
        """
        Returns the text label name associated with the given geometry name.
        """
        return parent_name + "_text"

    def _hoverable_tag(self):
        return "hoverable"

    def _create_text_label(self, text, node_path):
        """
        Returns a new text node path parented to the given node path.
        """
        text_node = panda3d.core.TextNode(self._text_label_name(node_path.getName()))
        text_node.setText(text)
        text_node.setCardColor(*self._color_from_viz3_rgba(core.RGBA.from_string("gray1")))
        text_node.setCardAsMargin(0.2, 0.2, 0.2, 0.2)
        text_node.setTextColor(*self._color_from_viz3_rgba(core.RGBA.from_string("gray8")))
        text_node.setWordwrap(20)

        # Point towards user; See
        # https://docs.panda3d.org/1.10/python/programming/render-effects/billboard?highlight=setdepthwrite#billboard-effects
        text_path = node_path.attachNewNode(text_node)
        text_path.setBillboardPointEye(-50, fixed_depth=True)
        text_path.setBin("fixed", 0)
        text_path.setDepthWrite(False)
        text_path.setDepthTest(False)

        node_path.setTag(self._hoverable_tag(), text_path.getName())

        text_path.stash()  # Hide until hovered
        return text_path

    def _text_label_from_parent(self, parent_node_path):
        """
        Given a parent node path, returns the corresponding text label node path
        associated, or an empty (.isEmpty()) node path if there is no associated
        text label.
        """
        text_label_name = self._text_label_name(parent_node_path.getName())

        # We .stash() text nodes that are not currently being displayed; these
        # are not given with .getChildren() and other children are not given
        # with .getStashedChildren()
        children_paths = list(parent_node_path.getStashedChildren()) + list(parent_node_path.getChildren())
        for child_node_path in children_paths:
            if child_node_path.getName() == text_label_name:
                return child_node_path

        return panda3d.core.NodePath()

    def _parent_from_text_label(self, text_node_path):
        """
        Given a text node path, returns the corresponding parent node path, if
        it exists.
        """
        tag = self._hoverable_tag()
        return text_node_path.findNetTag(tag)

    def _node_path_from_viz3_geometry(self, name, geometry):
        """
        Creates a new node from the given viz3 geometry.
        """
        # See https://docs.panda3d.org/1.10/python/programming/internal-structures/procedural-generation/index
        v_rgba_fmt = panda3d.core.GeomVertexFormat.get_v3cp()

        # Static -> We'll only be fillling in vertices once
        v_data = panda3d.core.GeomVertexData(":viz3geometry:", v_rgba_fmt, panda3d.core.Geom.UHStatic)
        v_data.setNumRows(len(geometry.vertexes()))
        v_col_writer = panda3d.core.GeomVertexWriter(v_data, 'vertex')
        v_color_writer = panda3d.core.GeomVertexWriter(v_data, 'color')
        for pt in geometry.vertexes():
            v_col_writer.addData3(utils.swap_yz_coords(pt))
            # Need to set color for each row
            v_color_writer.addData4(*self._color_from_viz3_rgba(geometry.color))

        triangle = panda3d.core.GeomTriangles(panda3d.core.Geom.UHStatic)
        geom = panda3d.core.Geom(v_data)
        for tri in geometry.triangles():
            triangle.addVertices(*tri)

        geom.addPrimitive(triangle)

        node = panda3d.core.GeomNode(name)
        node.addGeom(geom)
        node_path = self.render.attachNewNode(node)

        if geometry.hide_distance > 0 or geometry.show_distance < float("inf"):
            self._create_lod(name, node_path, geometry.hide_distance, geometry.show_distance)

        coord = utils.swap_yz_coords(geometry.pos)
        node_path.setPos(*coord)

        if geometry.text != "":
            self._create_text_label(geometry.text, node_path)

        # Attempt to fix culling issues with opacity; not entirely sure if
        # these help
        node_path.setTwoSided(True)
        if geometry.color.opacity < 1.0:
            node_path.setDepthWrite(False)

        return node_path

    def _move_node_path(self, node_path, new_pos):
        """
        Moves the given node path to the given position, positioning any
        children nodes with it.
        """
        node_path.setPos(new_pos)

    def _move_label_node_path_from_collision(self, collision_entry, label_node_path):
        """
        Posisitions the given text label to be where the ray collision occurred.
        """
        parent_node_path = self._parent_from_text_label(label_node_path)
        pos = collision_entry.getSurfacePoint(parent_node_path)
        label_node_path.setPos(pos)

    def _find_label_from_collision(self, collided_node_path):
        """
        Returns the Panda3D NodePath label associated with the collision, if
        one exists. Otherwise, an empty NodePath is returned.
        """
        tag = self._hoverable_tag()
        if collided_node_path.hasTag(tag):
            # if parent of label
            return self._text_label_from_parent(collided_node_path)

        # if label itself
        parent_node_path = self._parent_from_text_label(collided_node_path)
        if not parent_node_path:
            return parent_node_path  # not so; return empty

        return self._text_label_from_parent(parent_node_path)

    def _on_mouse_hover(self, task):
        """
        Creates on-screen text when an object that has some associated text is
        hovered over.

        task: direct.task.Task
            This task, represented in direct.task. Use task.time for timing
            purposes.

        See https://docs.panda3d.org/1.10/python/programming/tasks-and-events/tasks
        See https://docs.panda3d.org/1.10/cpp/programming/collision-detection/clicking-on-3d-objects
        See samples/chessboard in Panda3D repository
        """
        if not self.mouseWatcherNode.hasMouse():
            return direct.task.Task.cont

        mouse_pos = self.mouseWatcherNode.getMouse()
        self._mouse_collision_ray.setFromLens(self.camNode, mouse_pos.getX(), mouse_pos.getY())
        self._mouse_collision_picker.traverse(self.render)

        # Entries in queue are front-to-back that we collided with
        i = 0
        num_entries = self._mouse_collision_queue.getNumEntries()
        while i < num_entries:
            collision_entry = self._mouse_collision_queue.getEntry(i)
            i += 1

            # Could be label itself, ordinary node, or something with an associated label
            collided_node_path = collision_entry.getIntoNodePath()
            label_node_path = self._find_label_from_collision(collided_node_path)
            if not label_node_path:
                # e.g. we collided with something without a label (or a label
                #      itself); want the node behind that
                continue

            self._move_label_node_path_from_collision(collision_entry, label_node_path)
            if label_node_path == self._last_hovered_label_node_path:
                break

            if self._last_hovered_label_node_path:
                self._last_hovered_label_node_path.stash()

            label_node_path.unstash()
            self._last_hovered_label_node_path = label_node_path
            break

        else:
            # If no entries matched!
            if self._last_hovered_label_node_path:
                # Hide
                self._last_hovered_label_node_path.stash()
                self._last_hovered_label_node_path = None

        return direct.task.Task.cont

    def _color_from_viz3_rgba(self, rgb):
        """
        Returns a new Panda3d color from the given viz3 RGB color.
        """
        return rgb.r / 255, rgb.g / 255, rgb.b / 255, rgb.a / 255
