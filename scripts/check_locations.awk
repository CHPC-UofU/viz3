#!/usr/bin/awk -f
# Checks a location file from basic validity. POSIX awk compatible.
#
# A location file looks like:
# datacenter-room-pod-row-rack2
# 	host	optional-data	...				# 1U, slot 1
# 	%label							# *ignored*
#	host2,host3						# 1U, slot 2
#	host4							# 2U, slot 3
#	host4							# 2U, slot 4
# 	:label							# *skipped*
#	host5							# 1U, slot 6
# 	...
# datacenter-room-pod-row-rack2		# Declares rack, without contents
# 	%label1
# datacenter-room-pod-row-rack3		# Same as ^
# ...
#
# Specifically, this checker ensures the syntax is valid, as well as ensuring
# all the non-empty racks have the same number of slots. It also warns when
# machines are non-sequential in their racks, an indication of fat-fingering.
#
# Usage: ./check_locations.awk [location-file]
function die(last_words) {
    print last_words | "cat 1>&2"
    exit(1)
}
function warn(message) {
    print message | "cat 1>&2"
}
function num_from_target(target) {
    tmp = target
    gsub(/[^0-9]/, "", tmp)
    return int(tmp)
}
/^[ \t]*#/ {
    # ignore comments
    next
}
/^[a-zA-Z0-9_][a-zA-Z0-9_]*-[a-zA-Z0-9_][a-zA-Z0-9_]*-[a-zA-Z0-9_][a-zA-Z0-9_]*-[a-zA-Z0-9_][a-zA-Z0-9_]*-[a-zA-Z0-9_][a-zA-Z0-9_]*$/ {
    # rack section
    last_num = ""
    curr_rack = $1
    if (curr_rack in rack_count)
        die("New rack specified is same as previously seen: " curr_rack)

    rack_count[curr_rack] = 0
    next
}
/^[ \t]/ {
    # rack slot entry
    if ($1 ~ /^%/)  # data associated with rack, not in a slot. e.g. %pdu
        next

    rack_count[curr_rack]++

    if ($1 ~ /^:/)  # data that counts towards a slot, but is not a host. e.g. :space
        next

    n = split($1, targets, ",")  # slots may have one or more hosts in then. e.g. 4x2U
    if (n == 1) {
        num = num_from_target(targets[1])
        if (last_num && !(last_num == num || (last_num + 1 == num)))
            warn("Sibling slots are not monotonically increasing or the same: last=" last_num ", curr=" num " (" $1 ")")
    }
    else {
        # otherwise the logic checking is too complex for me in awk... use last
        # note: numbers are likely not sequential in a 4x2U; they may be flipped
        num = num_from_target(targets[n])
    }

    last_num = num
    next
}
{
    die("Encountered an unknown line (no leading space, nor a rack match): '" $0 "'")
}
END {
    prev_rack = ""
    prev_rack_count = 0
    code = 0
    for (rack in rack_count) {
        if (rack_count[rack] == 0)  # skip empty racks; they are used to indicate missing data
            continue

        if (prev_rack && rack_count[rack] != prev_rack_count) {
            warn("Rack " rack " count is not the same as previous rack " prev_rack ": " rack_count[rack] " (curr) vs " prev_rack_count " (prev)")
            code = 1
        }

        prev_rack = rack
        prev_rack_count = rack_count[rack]
    }
    exit(code)
}
