// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <pmp/SurfaceMesh.h>
#include <pmp/algorithms/SurfaceFactory.h>

#include "pmp.hpp"
#include "geometry.hpp"

namespace viz3::external {

static viz3::Point convert_pmp_point(const pmp::Point& pt)
{
    // our Z is their Y and vice versa
    return { pt[0], pt[2], pt[1] };
}

static viz3::Point convert_pmp_vertex(const pmp::SurfaceMesh& mesh, const pmp::Vertex& v)
{
    return convert_pmp_point(mesh.position(v));
}

static viz3::Face convert_pmp_face(const pmp::SurfaceMesh& mesh, const pmp::Face& face)
{
    std::array<unsigned int, 3> faces {};

    int i = 0;
    for (auto v : mesh.vertices(face)) {
        assert(i < 3);  // Not a triangle mesh!
        faces[i] = v.idx();
        i++;
    }

    return std::tuple_cat(faces);
}

static void convert_to_triangle_mesh(pmp::SurfaceMesh& mesh)
{
    // Shout out to the PMP-library folks who designed SurfaceMesh such that
    // we don't have to worry about iterator invalidation. Sooo much cleaner
    // code once I found this out...
    for (auto face : mesh.faces()) {
        auto num_vertices = mesh.valence(face);
        if (num_vertices <= 3)
            continue;

        /*
         *       o              o
         *    /    \         / |\ \
         *  o       o  ->  o   |\  o
         *   \     /        \ |  \/
         *    o--o            o--o
         *
         * By going in a circular pattern, we ensure there are no complex
         * vertexes (i.e. no overlap between faces)
         */

        // We must delete the face beforehand, otherwise we get a runtime
        // error complaining about a complex vertex
        std::vector<pmp::Vertex> fv {};
        fv.reserve(num_vertices);
        for (auto v : mesh.vertices(face))  // circular order
            fv.push_back(v);

        mesh.delete_face(face);

        int i = 1;
        auto num_triangles = num_vertices - 2;
        while (num_triangles > 0) {
            mesh.add_triangle(fv[0], fv[i], fv[i+1]);

            i++;
            num_triangles--;
        }
    }
}

static std::pair<std::vector<Point>, std::vector<Face>> convert_pmp_mesh(const pmp::SurfaceMesh& mesh, const Point& fixup_offset_pt)
{
    std::vector<Point> vertexes {};
    vertexes.reserve(mesh.vertices_size());
    for (auto v : mesh.vertices())
        vertexes.emplace_back(convert_pmp_vertex(mesh, v) + fixup_offset_pt);

    std::vector<Face> faces {};
    faces.reserve(mesh.faces_size());
    for (auto face : mesh.faces())
        faces.emplace_back(convert_pmp_face(mesh, face));

    return { vertexes, faces };
}

void SphereElement::render(const Path& path, std::shared_ptr<RenderTree> render_tree) const
{
    auto n_slices = num_circular_slices();
    auto sphere = pmp::SurfaceFactory::uv_sphere(pmp::Point(0, 0, 0), radius(), n_slices, n_slices);
    convert_to_triangle_mesh(sphere);

    auto [vertexes, faces] = convert_pmp_mesh(sphere, Point(radius(), 0, radius()));
    auto geometry = construct_geometry(move(vertexes), move(faces), Point());
    render_tree->update(path, geometry);
}

void CylinderElement::render(const Path& path, std::shared_ptr<RenderTree> render_tree) const
{
    auto n_slices = num_circular_slices();
    auto cylinder = pmp::SurfaceFactory::cylinder(n_slices, radius(), height());
    convert_to_triangle_mesh(cylinder);

    auto [vertexes, faces] = convert_pmp_mesh(cylinder, Point(radius(), 0, radius()));
    auto geometry = construct_geometry(move(vertexes), move(faces), Point());
    render_tree->update(path, geometry);
}

void ObjElement::render(const Path& path, std::shared_ptr<RenderTree> render_tree) const
{
    pmp::SurfaceMesh mesh;
    mesh.read(m_filepath);
    convert_to_triangle_mesh(mesh);

    auto mesh_bounds = mesh.bounds();
    auto offset_fixup = -mesh_bounds.min();
    auto [vertexes, faces] = convert_pmp_mesh(mesh, convert_pmp_point(offset_fixup));
    auto geometry = construct_geometry(move(vertexes), move(faces), Point());

    auto [width, height, depth] = geometry.bounds().lengths();
    geometry.scale_by(compute_scale_factor(width, height, depth));

    render_tree->update(path, geometry);
}

}
