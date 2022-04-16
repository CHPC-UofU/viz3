// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <stdexcept>
#include <limits>
#include <memory>
#include <chrono>

#include <pybind11/operators.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "../value_types.hpp"
#include "../box.hpp"
#include "../feature.hpp"
#include "../layout.hpp"
#include "../pmp.hpp"
#include "../viz3.hpp"

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace py = pybind11;
using namespace viz3;
using namespace viz3::external;

PYBIND11_MODULE(core, m)
{
    m.attr("__name__") = "viz3.core";
    m.doc() = R"pbdoc(
        Viz3: 3D Visualization tool for dynamic and reactive data sources.
        -----------------------
        .. currentmodule:: viz3.core
        .. autosummary::
           :toctree: _generate
    )pbdoc";

    m.def("is_valid_path_part", &is_valid_path_part, "Whether the given string is a valid part within a Path()");

    py::class_<Path>(m, "Path")
        .def(py::init<std::initializer_list<std::string>>())
        .def(py::init<std::vector<std::string>>())
        .def(py::init<const std::string&>())
        .def(py::init([](const py::args& args){
            std::vector<std::string> parts;
            for (auto& arg : args) {
                parts.push_back(arg.cast<std::string>());
            }
            return std::make_unique<Path>(parts);
        }))
        .def("parts", &Path::parts)
        .def("empty", &Path::empty)
        .def("first", &Path::first)
        .def("last", &Path::last)
        .def("without_first", &Path::without_first)
        .def("without_last", &Path::without_last)
        .def("without_common_ancestor", &Path::without_last)
        .def("is_child_of", &Path::is_child_of)
        .def("is_leaf", &Path::is_leaf)
        .def("is_descendant_of", py::overload_cast<const Path&, bool>(&Path::is_descendant_of, py::const_), py::arg("path"), py::arg("or_are_same") = false)
        .def("paths_between", &Path::paths_between, py::arg("path"), py::arg("including_self") = false)
        .def("ancestor_paths", &Path::ancestor_paths, py::arg("including_self") = false)
        .def("common_ancestor_with", &Path::common_ancestor_with)
        .def("child_of_common_ancestor_with", &Path::child_of_common_ancestor_with)
        .def("join_after_common_descendant", &Path::join_after_common_descendant, py::arg("path"))
        .def(py::self + std::string())
        .def(py::self + py::self)
        .def(py::self - py::self)
        .def(py::self == py::self)
        .def(py::self != py::self)
        .def(py::self < py::self)
        .def(py::self > py::self)
        .def(py::self <= py::self)
        .def(py::self >= py::self)
        .def(hash(py::self))
        .def("__len__", &Path::size)
        .def("__str__", &Path::string)
        .def("__repr__", [](const Path& path) {
            return std::string("viz3.core.Path(") + path.string() + std::string(")");
        });

    py::class_<color::RGBA>(m, "RGBA")
        .def(py::init<std::tuple<unsigned char, unsigned char, unsigned char>>())
        .def(py::init<std::tuple<unsigned char, unsigned char, unsigned char, float>>())
        .def(py::init<unsigned char, unsigned char, unsigned char>(), py::arg("r"), py::arg("g"), py::arg("b"))
        .def(py::init<unsigned char, unsigned char, unsigned char, float>(), py::arg("r"), py::arg("g"), py::arg("b"), py::arg("opacity"))
        .def(py::init<const color::RGBA&>())
        .def_static("from_string", &color::RGBA::from_string, py::arg("color"), py::arg("opacity") = 1.0)
        .def_readonly("r", &color::RGBA::r)
        .def_readonly("g", &color::RGBA::g)
        .def_readonly("b", &color::RGBA::b)
        .def_readonly("a", &color::RGBA::a)
        .def_property("opacity", &color::RGBA::opacity, &color::RGBA::set_opacity)
        .def("__str__", &color::RGBA::string)
        .def("__repr__", [](const color::RGBA& rgba) {
            return std::string("viz3.core.RGBA") + rgba.string();
        });

    py::class_<EventListener>(m, "EventListener")
        .def("poll", &EventListener::poll)
        .def("listen", [](EventListener* listener) -> std::optional<Event> {
            using namespace std::chrono_literals;

            // For long-running C++ code we should not hold the GIL, since
            // other threads may want to execute Python code
            // https://pybind11.readthedocs.io/en/stable/advanced/misc.html#global-interpreter-lock-gil
            py::gil_scoped_release release;
            std::optional<Event> maybe_event;
            while (!maybe_event) {
                {
                    py::gil_scoped_acquire acquire;
                    // Check if signal has been raised, since .listen() will cause all signals
                    // to be ignored because of a lock it holds (hence why we listen with a
                    // timeout); See https://pybind11.readthedocs.io/en/stable/faq.html?highlight=signal#how-can-i-properly-handle-ctrl-c-in-long-running-functions
                    if (PyErr_CheckSignals() != 0)
                        throw py::error_already_set();
                }

                auto event_server_died_and_maybe_event = listener->try_listen_for(150ms);
                if (event_server_died_and_maybe_event.first)
                    return {};

                maybe_event = event_server_died_and_maybe_event.second;
            }
            return maybe_event;
        })
        .def("token", &EventListener::token);

    py::enum_<EventType>(m, "EventType", py::arithmetic())
       .value("Add", EventType::Add)
       .value("Remove", EventType::Remove)
       .value("Move", EventType::Move)
       .value("Resize", EventType::Resize)
       .value("Recolor", EventType::Recolor)
       .value("Retext", EventType::Retext);

    py::class_<Event>(m, "Event")
        .def(py::init<Path, Geometry, EventType>())
        .def_readwrite("path", &Event::path)
        .def_readwrite("geometry", &Event::geometry)
        .def_readonly("type", &Event::type);

    py::class_<Node, std::shared_ptr<Node>>(m, "Node")
        .def_property_readonly("name", &Node::get_name)
        .def("path", &Node::path)
        .def_property("element", &Node::element, &Node::set_element)
        .def("construct_child", &Node::construct_child)
        .def("try_get_child", &Node::try_get_child)
        .def("has_child", &Node::has_child)
        .def("remove_child", &Node::remove_child)
        .def("find_descendant", &Node::find_descendant)
        .def("children_names", &Node::children_names)
        .def("construct_template", &Node::construct_template)
        .def("try_get_template", &Node::try_get_template)
        .def("try_make_template", &Node::try_make_template)
        .def("try_get_child_or_make_template", &Node::try_get_child_or_make_template)
        .def("template_names", &Node::template_names)
        .def("__str__", &Node::string);

    py::class_<RootNode, std::shared_ptr<RootNode>, Node>(m, "RootNode")
        .def("render_from_root", &RootNode::render_from_root);

    py::class_<NodeTransaction, std::shared_ptr<NodeTransaction>> node_transaction(m, "NodeTransaction");
    node_transaction.def(py::init<std::shared_ptr<RootNode>, std::weak_ptr<EventServer>>())
        .def("render", &NodeTransaction::render)
        .def("node", &NodeTransaction::node);

    py::enum_<EventFilter>(m, "EventFilter")
        .value("ReceiveAll", EventFilter::ReceiveAll)
        .value("SkipNonDrawable", EventFilter::SkipNonDrawable)
        .export_values();

    py::class_<LayoutEngine, std::shared_ptr<LayoutEngine>>(m, "LayoutEngine")
        .def(py::init<>())
        .def("request_listener", &LayoutEngine::request_listener, py::arg("filter") = EventFilter::SkipNonDrawable)
        .def("transaction", py::overload_cast<>(&LayoutEngine::transaction), py::return_value_policy::copy)
        .def("__str__", &LayoutEngine::string);

    py::class_<Point>(m, "Point")
        .def(py::init<>())
        .def(py::init<float, float, float>(), py::arg("x") = 0.0f, py::arg("y") = 0.0f, py::arg("z") = 0.0f)
        .def(py::init<std::tuple<float, float, float>>())
        .def_readwrite("x", &Point::x)
        .def_readwrite("y", &Point::y)
        .def_readwrite("z", &Point::z)
        .def(py::self + py::self)
        .def(py::self - py::self)
        .def(py::self == py::self)
        .def(py::self != py::self)
        .def(py::self < py::self)
        .def(py::self > py::self)
        .def(hash(py::self))
        .def("__getitem__", [](const Point& pt, unsigned int axis) {
            if (axis == 0)
                return pt.x;
            if (axis == 1)
                return pt.y;
            if (axis == 2)
                return pt.z;

            throw std::out_of_range("Axis given is not 0-2");
        })
        .def("__len__", [](const Point&) {
            return 3;
        })
        .def("__str__", &Point::string)
        .def("__repr__", [](const Point& pt) {
            return std::string("viz3.core.Point(") + pt.string() + std::string(")");
        });

    py::implicitly_convertible<std::tuple<float, float, float>, Point>();

    py::class_<Bounds>(m, "Bounds")
        .def(py::init<>())
        .def(py::init<std::pair<Point, Point>>())
        .def(py::init<Point, Point>())
        .def(py::init<float, float, float>())
        .def("base", &Bounds::base)
        .def("end", &Bounds::end)
        .def("center", &Bounds::center)
        .def("strip_pos", &Bounds::strip_pos)
        .def("lengths", &Bounds::lengths)
        .def("width", &Bounds::width)
        .def("height", &Bounds::height)
        .def("depth", &Bounds::depth)
        .def("rotate_around", &Bounds::rotate_around)
        .def(py::self == py::self)
        .def(py::self != py::self)
        .def(py::self += py::self)
        .def("__str__", &Bounds::string)
        .def("__repr__", [](const Bounds& bounds) {
            return std::string("viz3.core.Bounds(") + bounds.string() + std::string(")");
        });

    py::class_<Rotation>(m, "Rotation")
        .def(py::init<float>(), py::arg("degrees") = 0.0f)
        .def(py::init<float, float, float>(), py::arg("yaw"), py::arg("pitch"), py::arg("roll"))
        .def_static("none", &Rotation::none)
        .def(py::self * py::self)
        .def(py::self *= py::self)
        .def(py::self == py::self)
        .def(py::self != py::self)
        .def("rotate_coord", py::overload_cast<const Point&>(&Rotation::rotate_coord, py::const_))
        .def("rotation", &Rotation::rotation)
        .def("yaw", &Rotation::yaw)
        .def("pitch", &Rotation::pitch)
        .def("roll", &Rotation::roll);

    py::class_<Geometry>(m, "Geometry")
        .def(py::init<std::vector<Point>,
            std::vector<std::tuple<unsigned int, unsigned int, unsigned int>>,
            Point,
            color::RGBA,
            float,
            float,
            std::string>(), py::arg("vertexes"), py::arg("triangles"), py::arg("pos"), py::arg("color") = color::default_color, py::arg("hide_distance") = 0.0f, py::arg("show_distance") = std::numeric_limits<float>::infinity(), py::arg("text") = "")
        .def_static("empty", &Geometry::empty, py::arg("pos"), py::arg("bounds"), py::arg("color") = color::default_color, py::arg("text") = std::nullopt)
        .def("combine_with", &Geometry::combine_with, py::arg("other_geometry"))
        .def("bounds", &Geometry::bounds)
        .def("positioned_bounds", &Geometry::positioned_bounds)
        .def("should_draw", &Geometry::should_draw)
        .def("vertexes", &Geometry::vertexes)
        .def("triangles", &Geometry::triangles)
        .def("rotate_around", &Geometry::rotate_around)
        .def("stretch_by", &Geometry::stretch_by)
        .def("scale_by", &Geometry::scale_by)
        .def_property("color", &Geometry::color, &Geometry::set_color)
        .def_property("pos", &Geometry::pos, &Geometry::set_pos)
        .def_property("hide_distance", &Geometry::hide_distance, &Geometry::set_hide_distance)
        .def_property("show_distance", &Geometry::show_distance, &Geometry::set_show_distance)
        .def_property("text", &Geometry::text, &Geometry::set_text);

    // Features are not allowed to be constructible, they are simply mixins for
    // Elements. So don't create a constructor and don't export things like
    // attributes() methods, which Elements provide.
    //
    // Features must also have shared pointer holders, despite not being allowed
    // to be constructible, since Element classes, which have shared pointer
    // holders, inherit from them.
#define FEATURE(Feature) \
    py::class_<Feature, std::shared_ptr<Feature>>(m, MACRO_STRINGIFY(Feature))

    FEATURE(TextFeature)
        .def_property("text", &TextFeature::text, &TextFeature::set_text);

    FEATURE(SizeFeature)
        .def_property("width", &SizeFeature::width, &SizeFeature::set_width)
        .def_property("height", &SizeFeature::height, &SizeFeature::set_height)
        .def_property("depth", &SizeFeature::depth, &SizeFeature::set_depth)
        .def("lengths", &SizeFeature::lengths)
        .def("axis_length", &SizeFeature::axis_length);

    FEATURE(ColorFeature)
        .def_property("color", &ColorFeature::color, &ColorFeature::set_color)
        .def_property("darkness", &ColorFeature::darkness, &ColorFeature::set_darkness)
        .def("compute_color", &ColorFeature::compute_color);

    FEATURE(OpticsFeature)
        .def_property("opacity", &OpticsFeature::opacity, &OpticsFeature::set_opacity);

    FEATURE(HideShowFeature)
        .def_property("hide_distance", &HideShowFeature::hide_distance, &HideShowFeature::set_hide_distance)
        .def_property("show_distance", &HideShowFeature::show_distance, &HideShowFeature::set_show_distance)
        .def("hide_and_show_distances", &HideShowFeature::hide_and_show_distances)
        .def_property("clamp_descendant_hide_distances", &HideShowFeature::clamp_descendant_hide_distances, &HideShowFeature::set_clamp_descendant_hide_distances)
        .def_property("clamp_descendant_show_distances", &HideShowFeature::clamp_descendant_show_distances, &HideShowFeature::set_clamp_descendant_show_distances);

    FEATURE(RotateFeature)
        .def_property("rotation", &RotateFeature::rotation, &RotateFeature::set_rotation);

    FEATURE(PaddingFeature)
        .def_property("padding", &PaddingFeature::padding, &PaddingFeature::set_padding);

    FEATURE(SpacingFeature)
        .def_property("spacing", &SpacingFeature::spacing, &SpacingFeature::set_spacing);

    FEATURE(AxisFeature)
        .def_property("axis", &AxisFeature::axis, &AxisFeature::set_axis);

    FEATURE(AlignFeature)
        .def_property("align", &AlignFeature::alignment, &AlignFeature::set_alignment);

    FEATURE(CircularFeature)
        .def_property("radius", &CircularFeature::radius, &CircularFeature::set_radius)
        .def_property("detail", &CircularFeature::detail, &CircularFeature::set_detail)
        .def_property_readonly("num_circular_slices", &CircularFeature::num_circular_slices);

    py::class_<AbstractElement, std::shared_ptr<AbstractElement>>(m, "AbstractElement")
        .def_property("name", &AbstractElement::get_name, &AbstractElement::set_name)
        .def("render", &AbstractElement::render)
        .def("clone", &AbstractElement::clone)
        .def("render", &AbstractElement::render)
        .def("update_from_attributes", &AbstractElement::update_from_attributes)
        .def("attributes", &AbstractElement::attributes)
        .def("update_ancestor_values", &AbstractElement::update_ancestor_values);

    // Normally these Elements inherit from BaseElement, but that is a
    // template, so we must annotate the Feature inheritances here
    //
    // Note that if no Feature base type is provided here (e.g. only
    // py::class_<SomeElement, std::shared_ptr<SomeElement>(m, ...)), then see
    // https://pybind11.readthedocs.io/en/stable/advanced/classes.html#multiple-inheritance
#define ELEMENT(Element, ...) \
    py::class_<Element, std::shared_ptr<Element>, __VA_ARGS__, AbstractElement>(m, MACRO_STRINGIFY(Element), py::multiple_inheritance()) \
        .def(py::init<std::string, const AttributeMap&>(), py::arg("name"), py::arg("attributes")) \
        .def(py::init([](const std::string& name, const py::kwargs& kwargs) { \
            AttributeMap map {}; \
            for (auto& kv : kwargs) \
                map.insert_or_assign(py::str(kv.first), py::str(kv.second)); \
            return Element(name, map); \
        }))

#define MESH_FEATURES TextFeature, ColorFeature, OpticsFeature, HideShowFeature
#define MESH_ELEMENT(Element, ...) \
    ELEMENT(Element, MESH_FEATURES, __VA_ARGS__)

    MESH_ELEMENT(BoxElement, SizeFeature)
        .def("box_geometry", &BoxElement::box_geometry);

    MESH_ELEMENT(PlaneElement, SizeFeature, PaddingFeature);

    ELEMENT(NoLayoutElement, SizeFeature);

    ELEMENT(GridElement, SpacingFeature);

    ELEMENT(ScaleElement, SizeFeature, AxisFeature);

    ELEMENT(HideShowElement, HideShowFeature);

    ELEMENT(RotateElement, RotateFeature);

    ELEMENT(JuxtaposeElement, AxisFeature, SpacingFeature, AlignFeature);

    ELEMENT(PaddingElement, PaddingFeature, SizeFeature);

    ELEMENT(StreetElement, SpacingFeature, AxisFeature);

    MESH_ELEMENT(SphereElement, CircularFeature);

    MESH_ELEMENT(CylinderElement, CircularFeature, SizeFeature);

    MESH_ELEMENT(ObjElement, SizeFeature);

#ifdef VERSION_INFO
    m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
    m.attr("__version__") = "dev";
#endif
}
