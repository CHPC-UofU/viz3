// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include <ostream>

#include "path.hpp"
#include "viz3.hpp"
#include "transaction.hpp"

namespace viz3 {


std::ostream& operator<<(std::ostream& os, const LayoutEngine& engine)
{
    os << "LayoutEngine(): " << *engine.m_root_node;
    return os;
}

std::shared_ptr<NodeTransaction> LayoutEngine::transaction()
{
    /*
     * Here, we want to make sure that changes to the tree and updates, as
     * well as renders of the RenderTree are only made by one thread. So
     * lock the mutex here and unlock it when the transaction is done.
     */
    m_exclusive_transaction_mutex.lock();
    auto transaction = new NodeTransaction(m_root_node, event_server());
    return std::shared_ptr<NodeTransaction>(transaction, [&](NodeTransaction* t) {
        m_exclusive_transaction_mutex.unlock();
        delete t;
    });
}

std::unique_ptr<EventListener> LayoutEngine::request_listener(EventFilter filter)
{
    return m_event_server->request_listener(filter);
}

std::string LayoutEngine::string() const
{
    std::stringstream stream;
    stream << *this;
    return stream.str();
}

}
