// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once

#include <memory>
#include <ostream>
#include <string>
#include <utility>

#include "event.hpp"
#include "node.hpp"
#include "transaction.hpp"

namespace viz3 {

/*
 * Core type that enables users to build a tree hierarchy of Elements and
 * renders them.
 *
 * Changes to the tree are done in a transaction, via the transaction() method,
 * and code (on a separate thread) that wants to receive goemetry changes to the
 * tree can do so with the request_listener() method.
 */
class LayoutEngine {
public:
    explicit LayoutEngine()
        : m_event_server(EventServer::construct())
        , m_render_tree(std::make_shared<RenderTree>())
        , m_root_node(RootNode::construct(m_render_tree))
        , m_exclusive_transaction_mutex() {};

    std::shared_ptr<NodeTransaction> transaction();
    std::unique_ptr<EventListener> request_listener(EventFilter filter = EventFilter::SkipNonDrawable);

    std::string string() const;
    friend std::ostream& operator<<(std::ostream&, const LayoutEngine&);

private:
    friend class NodeTransaction;
    std::weak_ptr<EventServer> event_server()
    {
        // This is a bit weird, but we cannot simply return a copy of our
        // shared_ptr without issue. The problem is the event server inherits
        // from std::enable_shared_from_this<>(), but that is not initialized
        // until the shared_ptr that constructed that object calls
        // enable_from_this() (for us we do that in weak_ptr()). This is
        // deeply confusing and I don't understand why I have to do it this
        // way...
        return m_event_server->weak_ptr();
    }

    std::shared_ptr<EventServer> m_event_server;
    std::shared_ptr<RenderTree> m_render_tree;
    std::shared_ptr<RootNode> m_root_node;
    std::recursive_mutex m_exclusive_transaction_mutex;
};

}
