#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2021-2022 Center for High Performance Computing <dylan.gardner@utah.edu>
# SPDX-License-Identifier: GPL-2.0-only
#
# Generates a physical datacenter infrastructure sqlite3 database containing
# the location of one or more machine types and their manufacturer/models.
#
# Python 2.7 will probably work in a pinch, but Python 3 is suggested.
#
# Usage: ./make-infradb.py location-file manufacturer_file table:host-file [table:host-file ...] infra-db
import argparse
import collections
import re
import sqlite3


Rack = collections.namedtuple("Rack", "datacenter room pod row rack")
RackEntry = collections.namedtuple("RackEntry", "rack host")
SlotEntry = collections.namedtuple("SlotEntry", "rack slot partition host")
Manufacturer = collections.namedtuple("Manufacturer", "manufacturer model units")


def manufacturers_from_file(filepath):
    """
    Returns a dictionary mapping hosts to a Manufacturer tuple from a
    quad tab-seperated file containing host, manufacturer, model, and size units.
    """
    host_manufacturers = {}
    with open(filepath) as f:
        for line in f.readlines():
            host, manufacturer, model, units = line.strip().split("\t")
            manufacturer = Manufacturer(manufacturer, model, units)
            if host in host_manufacturers:
                exit("Duplicate manufacturer entry for {}: {} vs {}"
                     .format(host, manufacturer, host_manufacturers[host]))

            host_manufacturers[host] = manufacturer

    return host_manufacturers


comment_re = r"^[ \t]*#"
id_re = r"[a-zA-Z0-9_][a-zA-Z0-9_]*"
rack_re = r"^(?P<datacenter>{})-(?P<room>{})-(?P<pod>{})-(?P<row>{})-(?P<rack>{})$".format(
    id_re,
    id_re,
    id_re,
    id_re,
    id_re
)
slot_re = r"^[ \t][ \t]*(?P<partitions>[^ \t][^ \t]*)"


def parse_locations(location_file):
    """
    Parses a location file and returns a tuple of Rack(s), RackEntry(s), and
	SlotEntry(s).
    """
    rack_sizes = {}
    racks = []
    rack_entries = []
    slot_entries = []
    with open(location_file) as f:
        rack = None
        slot_num = 0
        for line in f.readlines():
            line = line.rstrip()
            if re.match(comment_re, line) is not None:
                continue

            rack_match = re.match(rack_re, line)
            if rack_match is not None:
                rack = Rack(
                    rack_match.group("datacenter"),
                    rack_match.group("room"),
                    rack_match.group("pod"),
                    rack_match.group("row"),
                    rack_match.group("rack"),
                )
                if not racks or rack != racks[-1]:
                    rack_sizes[rack] = slot_num
                    slot_num = 0
                    racks.append(rack)

                continue

            slot_match = re.match(slot_re, line)
            if slot_match is not None:
                if not rack:
                    exit("Slot entry '{}' defined before any rack".format(line))

                partitions = slot_match.group("partitions")
                if partitions.startswith("%"):
                    rack_entries.append(RackEntry(rack, partitions.lstrip("%")))
                    continue

                if not partitions.startswith(":"):
                    partition_and_hosts = enumerate(partitions.split(","))
                    for partition, host in partition_and_hosts:
                        slot_entries.append(SlotEntry(rack, slot_num, partition, host))

                slot_num += 1
                continue

            exit("Encountered an unknown line (no leading space, nor a rack match): '{}'".format(line))

        rack_size = max(rack_sizes[rack] for rack in racks)
        fixed_slot_entries = []
        for slot_entry in slot_entries:
            rack = slot_entry.rack
            fixed_slot_entries.append(SlotEntry(rack, rack_size - slot_entry.slot, slot_entry.partition, slot_entry.host))

    return racks, rack_entries, fixed_slot_entries


def hosts_from_file(filepath):
    """
    Returns a list of newline-seperated hosts from a file.
    """
    hosts = []
    with open(filepath) as f:
        for line in f.readlines():
            hosts.append(line.strip())
    return hosts


def tables_and_hosts_from_file_args(table_host_filepaths):
    """
    Returns a dictionary mapping table names from table:machine_file arguments
    to a set of hosts found in the machine_file.
    """
    table_hosts = {}
    for table_host_filepath in table_host_filepaths:
        parts = table_host_filepath.split(":")
        table_name, host_filepath = parts[0], "".join(parts[1:])

        if not re.match(r"[a-zA-Z_][a-zA-Z0-9_]*", table_name):
            exit("Table name '{}' within '{}' is not an identifier "
                 "(/[a-zA-Z_][a-zA-Z0-9_]*/)"
                 .format(table_name, table_host_filepath))

        table_hosts[table_name] = set(hosts_from_file(host_filepath))

    return table_hosts


def unique_entries(slot_entries):
    """
    Returns a set of slots and partitions within all the slot entries that are
    unique.
    """
    unique_slots = set()
    unique_partitions = set()

	# If racks have no entries/slots in them, we still want at least one
    # location table entry
    unique_slots.add(0)
    unique_partitions.add(0)

    for slot in slot_entries:
        unique_slots.add(slot.slot)
        unique_partitions.add(slot.partition)

    return unique_slots, unique_partitions


def create_schema(cursor, table_names):
    """
    Creates the infrastructure database schema. The table names of machine
    types must be provided.
    """
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("CREATE TABLE IF NOT EXISTS location(datacenter TEXT, room TEXT, pod INTEGER, row TEXT, rack INTEGER, slot INTEGER, partition INTEGER, PRIMARY KEY(datacenter, row, rack, slot, partition));")
    for table_name in table_names:
        cursor.execute("CREATE TABLE IF NOT EXISTS {}(hostname TEXT, datacenter TEXT, row TEXT, rack INTEGER, slot INTEGER, partition INTEGER, FOREIGN KEY(datacenter, row, rack, slot, partition) REFERENCES location(datacenter, row, rack, slot, partition), PRIMARY KEY(hostname));".format(table_name))
        cursor.execute("CREATE TABLE IF NOT EXISTS {}_manufacturer(hostname TEXT, manufacturer TEXT, model TEXT, units INTEGER, PRIMARY KEY(hostname) FOREIGN KEY(hostname) REFERENCES {}(hostname));".format(table_name, table_name))


def main(args):
    conn = sqlite3.connect(args.infradb)
    cursor = conn.cursor()

    host_manufacturers = manufacturers_from_file(args.manufacturer_file)

    table_hosts = tables_and_hosts_from_file_args(args.__dict__["table:host-file"])

    racks, rack_entries, slot_entries = parse_locations(args.location_file)

    create_schema(cursor, set(table_hosts))

    # Our visualization example(s) requires these stub entries to exist, even
    # if there is no corresponding machine in a particular slot or rack
    unique_slots, unique_partitions = unique_entries(slot_entries)
    for rack in racks:
        for slot in unique_slots:
            for partition in unique_partitions:
                cursor.execute("REPLACE INTO location(datacenter, room, pod, row, rack, slot, partition) VALUES(?, ?, ?, ?, ?, ?, ?)", (rack.datacenter, rack.room, rack.pod, rack.row, rack.rack, slot, partition))

    for table_name, hosts in table_hosts.items():
        for rack_entry in rack_entries:
            if rack_entry.host in hosts:
                conn.execute("REPLACE INTO {}(hostname, datacenter, row, rack, slot, partition) VALUES(?, ?, ?, ?, ?, ?)".format(table_name), (rack_entry.host, rack_entry.rack.datacenter, rack_entry.rack.row, rack_entry.rack.rack, 0, 0))
                if rack_entry.host in host_manufacturers:
                    conn.execute("REPLACE INTO {}_manufacturer(hostname, manufacturer, model, units) VALUES(?, ?, ?, ?)".format(table_name), (rack_entry.host,) + host_manufacturers[rack_entry.host])

    for table_name, hosts in table_hosts.items():
        for slot_entry in slot_entries:
            if slot_entry.host in hosts:
                conn.execute("REPLACE INTO {}(hostname, datacenter, row, rack, slot, partition) VALUES(?, ?, ?, ?, ?, ?)".format(table_name), (slot_entry.host, slot_entry.rack.datacenter, slot_entry.rack.row, slot_entry.rack.rack, slot_entry.slot, slot_entry.partition))
                if slot_entry.host in host_manufacturers:
                    conn.execute("REPLACE INTO {}_manufacturer(hostname, manufacturer, model, units) VALUES(?, ?, ?, ?)".format(table_name), (slot_entry.host,) + host_manufacturers[slot_entry.host])

    cursor.close()
    conn.commit()


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("location_file",
                        help="The 'Location File' (see locations.txt)")
    parser.add_argument("manufacturer_file",
                        help="A tab seperated file containing host, "
                             "manufacturer, model tuples")
    parser.add_argument("table:host-file", nargs="+",
                        help="A newline-seperated file of hostnames, with the "
                             "'table:' being the corresponding SQL table name "
                             "to create/update")
    parser.add_argument("infradb", help="The sqlite3 database to create or update")

    return parser.parse_args()


if __name__ == "__main__":
    main(arguments())
