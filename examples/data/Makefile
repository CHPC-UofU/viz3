# POSIX Makefile for generating artifacts for viz3 examples.
#
# Makefile review:
# MACRO=value
#
# target: dependency1 dependency2
#     create $(MACRO) $< -o $@
#
# In the example above, $< is the dependencies, $@ is the target. MACRO is
# inserted wherever $(MACRO) is. If the target is not an actual file produced,
# .PHONY: should be used above it to tell make not to look for that file/dep.
#
# The first target in the Makefile is the default dependency (when 'make' is
# ran without any arguments). Typically 'all'.
#
# .SUFFIXES: .FROM .TO
# .FROM.TO:
#     convert $< > $@
#
# The example above is a conversion from the .FROM extension to the .TO
# extension using whatever 'convert' is. Running 'make file.TO' will result in
# file.FROM being converted to file.TO using whatever the 'convert' command
# is. In addition, if a target requires a dependency.TO file, and a
# dependency.FROM exists, a conversion will occur.
.POSIX:

SHELL=/bin/bash
PYTHON=python3  # python2 will *technically* work for make-infradb.py

all: required_artifacts

.PHONY: required_artifacts
required_artifacts: infra.db

locations.txt:
	../../scripts/check_locations.awk $@

infra.db: locations.txt manufacturers.txt pdus.txt machines.txt envs.txt
	rm $@
	$(PYTHON) ../../scripts/make-infradb.py locations.txt manufacturers.txt pdu:pdus.txt machine:machines.txt env:envs.txt $@

.PHONY: clean
clean:
	rm -f infra.db
