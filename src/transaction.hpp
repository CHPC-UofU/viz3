// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <memory>
#include <utility>

#include "event.hpp"
#include "node.hpp"

namespace viz3 {

/*
 * A class for manipulating multiple nodes in the LayoutEngine without triggering
 * re-renders.
 *
 * Developer Notes:
 * - We don't render() the transaction in the destructor since destructors
 *   are not supposed to fail and we can fail to commit a transaction if the
 *   LayoutEngine is destroyed.
 * - Still needs work to ensure multiple changes to the LayoutEngine are
 *   atomic and conflicts are handled... Currently there is no rollback
 *   mechanism.
 */
class NodeTransaction {
public:
    NodeTransaction(std::shared_ptr<RootNode> root_node, std::weak_ptr<EventServer> event_server)
        : m_old_render_tree(*(root_node->render_tree()))
        , m_root_node(std::move(root_node))
        , m_event_server_weak_ptr(std::move(event_server)) {
            // FIXME: We don't have any proper cache invalidation logic in the render
            //        tree, so when we update things, problems arise. Temporarily
            //        ignoring the problem for now:
            m_root_node->render_tree()->invalidate_parent_and_child_pos(m_root_node->path());
        };

    // [[nodiscard]] -> Ask compiler to warn if someone assumes this will always succeed!
    [[nodiscard]] bool render()
    {
        m_root_node->render_from_root();
        return try_update_events_based_on_render_tree_differences();
    }
    std::shared_ptr<RootNode> node() { return m_root_node; }

private:
    bool try_update_events_based_on_render_tree_differences()
    {
        auto new_render_tree = m_root_node->render_tree();
        auto differences = new_render_tree->differences_from(m_old_render_tree);

        // At any point the event server may be destroyed in another thread,
        // thus we need a "lock()" that returns a shared_ptr to ensure we don't
        // suddenly use a invalid ptr (since shared_ptr keeps the object alive,
        // even across threads).
        std::shared_ptr<EventServer> shared_event_server = m_event_server_weak_ptr.lock();
        if (!shared_event_server)
            return false;

        for (const auto& path_and_difference : differences) {
            auto& [path, difference] = path_and_difference;

            switch (difference) {
            case RenderDifferences::FirstMissing:
                shared_event_server->construct_event(path, *m_old_render_tree.get(path), EventType::Remove);
                break;
            case RenderDifferences::SecondMissing:
                shared_event_server->construct_event(path, *new_render_tree->get(path), EventType::Add);
                break;
            case RenderDifferences::Pos:
                shared_event_server->construct_event(path, *new_render_tree->get(path), EventType::Move);
                break;
            case RenderDifferences::Bounds:
                shared_event_server->construct_event(path, *new_render_tree->get(path), EventType::Resize);
                break;
            case RenderDifferences::Color:
                shared_event_server->construct_event(path, *new_render_tree->get(path), EventType::Recolor);
                break;
            case RenderDifferences::Text:
                shared_event_server->construct_event(path, *new_render_tree->get(path), EventType::Retext);
                break;
            }
        }
        return true;
    }

    const RenderTree m_old_render_tree;
    std::shared_ptr<RootNode> m_root_node;
    // weak -> if event server goes away don't keep it alive, just fail the transactions
    std::weak_ptr<EventServer> m_event_server_weak_ptr;
};

}
