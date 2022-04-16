// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <utility>

#include "path.hpp"
#include "geometry.hpp"

namespace viz3 {

// Stores the delta change type that thin clients should act on
// Remember to update bindings.cpp if modified!
enum class EventType {
    Add = 0,
    Remove,
    Move,
    Resize,
    Recolor,
    Retext,
};

struct Event {
    Path path;
    Geometry geometry;
    EventType type;
};

class EventListener;

enum class EventFilter {
    ReceiveAll,
    SkipNonDrawable,
};

// Note that enable_shared_from_this requires that EventServer is only
// instatiated with make_shared. We do this in LayoutEngine with construct();
class EventServer : public std::enable_shared_from_this<EventServer> {
public:
    using ListenerToken = unsigned int;

    std::unique_ptr<EventListener> request_listener(EventFilter filter);
    void release_listener(ListenerToken token);
    std::optional<Event> try_pop_event(ListenerToken token);
    Event wait_for_event(ListenerToken token);
    std::optional<Event> try_wait_for_event_for(ListenerToken token, std::chrono::milliseconds ms);

    static std::shared_ptr<EventServer> construct()
    {
        // Cannot use make_shared since that requires a public constructor
        return std::shared_ptr<EventServer>(new EventServer());
    }
    std::weak_ptr<EventServer> weak_ptr() { return weak_from_this(); };

private:
    explicit EventServer() = default;

    friend class NodeTransaction;
    void add_event(Event&& event);
    void construct_event(const Path& path, const Geometry& geometry, EventType type);

    bool event_available(ListenerToken token);
    Event pop_event(ListenerToken token);

    using EventIndex = size_t;
    struct ListenerPosition {
        EventFilter filter;
        EventIndex index;
    };

    EventIndex index_of_next_event(ListenerPosition pos);

    std::vector<Event> m_events;
    std::recursive_mutex m_event_mutex;
    std::condition_variable_any m_cond_var;
    std::unordered_map<ListenerToken, ListenerPosition> m_listener_pos;
    ListenerToken m_token_counter = 0;
};

class EventListener {
public:
    EventListener(std::weak_ptr<EventServer> event_server, EventServer::ListenerToken token)
        : m_event_server(std::move(event_server))
        , m_token(token) {};
    virtual ~EventListener();

    /*
     * Returns whether the event server disappeared and an event if it is
     * available.
     */
    std::pair<bool, std::optional<Event>> poll();
    /*
     * Blocks until an event is available, or until the event server
     * disappears.
     */
    std::optional<Event> listen();
    std::pair<bool, std::optional<Event>>  try_listen_for(std::chrono::milliseconds);
    EventServer::ListenerToken token() const { return m_token; }

private:
    std::weak_ptr<EventServer> m_event_server;
    EventServer::ListenerToken m_token;
};

}
