// SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
// SPDX-License-Identifier: GPL-2.0-only
#include "event.hpp"

namespace viz3 {

std::unique_ptr<EventListener> EventServer::request_listener(EventFilter filter)
{
    std::unique_lock<std::recursive_mutex> lock(m_event_mutex);

    auto token = m_token_counter++;
    auto pos = ListenerPosition { filter, 0 };
    m_listener_pos.emplace(token, pos);
    return std::make_unique<EventListener>(weak_from_this(), token);
}

void EventServer::release_listener(ListenerToken token)
{
    std::unique_lock<std::recursive_mutex> lock(m_event_mutex);

    if (m_listener_pos.count(token) > 0)
        m_listener_pos.erase(token);
}

std::optional<Event> EventServer::try_pop_event(ListenerToken token)
{
    std::unique_lock<std::recursive_mutex> lock(m_event_mutex);

    if (!event_available(token))
        return {};

    return pop_event(token);
}

void EventServer::add_event(Event&& event)
{
    std::unique_lock<std::recursive_mutex> lock(m_event_mutex);
    m_events.emplace_back(event);
    lock.unlock();

    m_cond_var.notify_all();
}

void EventServer::construct_event(const Path& path, const Geometry& geometry, EventType type)
{
    add_event({ path, geometry, type });
}

EventServer::EventIndex EventServer::index_of_next_event(ListenerPosition pos)
{
    EventIndex index = pos.index;
    while (index < m_events.size()) {
        bool event_is_drawable = m_events.at(index).geometry.should_draw();
        if (pos.filter == EventFilter::SkipNonDrawable && !event_is_drawable) {
            index++;
            continue;
        }
        break;
    }
    return index;
}

bool EventServer::event_available(ListenerToken token)
{
    auto pos = m_listener_pos.at(token);
    auto index = index_of_next_event(pos);
    return index < m_events.size();
}

Event EventServer::pop_event(ListenerToken token)
{
    // FIXME: We should remove events that all listeners have already recieved,
    //        and that new listeners don't need (because they have been overwritten...)
    ListenerPosition& pos = m_listener_pos.at(token);
    auto event_index = index_of_next_event(pos);
    auto event = m_events.at(event_index);
    pos.index = event_index + 1;
    return event;
}

Event EventServer::wait_for_event(ListenerToken token)
{
    std::unique_lock<std::recursive_mutex> lock(m_event_mutex);
    m_cond_var.wait(lock, [&] { return event_available(token) ; });
    return pop_event(token);
}

std::optional<Event> EventServer::try_wait_for_event_for(ListenerToken token, std::chrono::milliseconds ms)
{
    std::unique_lock<std::recursive_mutex> lock(m_event_mutex);
    if (!m_cond_var.wait_for(lock, ms, [&] { return event_available(token); }))
        return {};

    return try_pop_event(token);
}

std::pair<bool, std::optional<Event>> EventListener::poll()
{
    auto shared_event_server = m_event_server.lock();
    if (!shared_event_server)
        return { true, {} };

    return { false, shared_event_server->try_pop_event(m_token) };
}

std::optional<Event> EventListener::listen()
{
    auto shared_event_server = m_event_server.lock();
    if (!shared_event_server)
        return {};

    return shared_event_server->wait_for_event(m_token);
}

std::pair<bool, std::optional<Event>> EventListener::try_listen_for(std::chrono::milliseconds ms)
{
    auto shared_event_server = m_event_server.lock();
    if (!shared_event_server)
        return { true, {} };

    return { false, shared_event_server->try_wait_for_event_for(m_token, ms) };
}

EventListener::~EventListener()
{
    // FIXME: Maybe these actions can be done with the optional destructor action in
    //        shared_ptr<>, since we only use that?
    auto shared_event_server = m_event_server.lock();
    if (shared_event_server) {
        // When a listener is destructed we need notify the event server so it can
        // delete the appropriate resources allocated to it
        shared_event_server->release_listener(m_token);
        return;
    }
    m_event_server.~weak_ptr();
}

}
