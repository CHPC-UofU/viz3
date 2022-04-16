# POSIX Makefile for running viz3 examples.
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
# must be same as specified with cmake -DPYBIND11_PYTHON_VERSION=...
PYTHON=python3
RENDERER=--web 8493 # or --panda3d

# chpc- if on CHPC's internal repo
PREFIX=
DATADIR=$(PREFIX)data
CONFDIR=$(PREFIX)conf

machine_room_simple: required_artifacts $(CONFDIR)/viz3.yaml models/machine_room.simple.xml
	$(PYTHON) viz-runner.py $(RENDERER) $(CONFDIR)/viz3.yaml models/machine_room.simple.xml

machine_room_full: required_artifacts $(CONFDIR)/viz3.yaml models/machine_room.xml
	$(PYTHON) viz-runner.py $(RENDERER) $(CONFDIR)/viz3.yaml models/machine_room.xml

motherboard:
	# The visualization is best shown with a 4U chassis; cluster271 is one of the few hosts with this
	$(PYTHON) viz-runner.py $(RENDERER) $(CONFDIR)/viz3.yaml models/redfish-motherboard.tall.xml redfish:instance=cluster271

.PHONY: required_artifacts
required_artifacts:
	make -C $(DATADIR) all

.PHONY: clean
clean:
	make -C $(DATADIR) clean
