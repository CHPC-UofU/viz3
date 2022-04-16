# viz3

This repository stores the viz3 software framework. The viz3 framework is an experimental tool designed to enable system administrators to be able to easily create 3D visualizations of their operational data, stored across time-series and relational databases. It uses [Panda3D](https://www.panda3d.org) to display visualizations on the desktop, and [three.js](http://threejs.org) on the web.

The viz3 framework is described in a paper called, ["viz3: Live 3D Visualizations of Data Acquisition with Changing Boundaries"](paper/viz3.pdf).

The visualizations in the paper can be recreated using cached data, since the paper visualizations were largely created using data from CHPC's Production time-series databases. See the [Docker section](#docker) or [Examples section](#examples) for details.

**Note:** There is currently no planned support for this software, and it is provided as-is.

## viz3

### Downloading

When cloning the repository make sure to include submodules:

```bash
git clone --recurse-submodules git@github.com:CHPC-UofU/viz3.git
```

If already cloned, the following command can be used to download the submodules:

```bash
git submodule update --init --recursive
```

### Docker

A Dockerfile is provided that runs an example machine room visualization, similar to the one shown in the paper:

```bash
docker build -t viz3 -f Dockerfile ./  # Build
docker run -i -p 8493:8493 viz3  # Run
# open localhost:8493 to see the visualization on the web
```

Other visualizations can be ran via:

```bash
# To produce the motherboard visualization in the paper:
docker run -p 8493:8493 -w /app/examples viz3 make motherboard
# or to produce the full machine room visualization:
# (this may take 15+ mins, due to a severe lack of optimizations in the framework at the moment)
docker run -p 8493:8493 -w /app/examples viz3 make machine_room_full
# or experimental per-process visualization
docker run -p 8493:8493 -w /app/examples viz3 python3 viz-realtime-procs.py
```

### Prerequesites

1. C++17 compilier (e.g. GCC 5 or higher)
2. CMake 3.4+
3. Python 3.9 or higher
4. Python development libraries (on MacOS `brew install python3` works)
5. Python modules found in requirements.txt
6. C++ Boost libraries (we are using Boost QVM)

To install the Python modules, simply do:

```bash
python3 -m pip install -r requirements.txt  # --user
```

The following worked on a desktop Ubuntu 21.04 box:

```bash
sudo apt install gcc python3-pip libpython3-dev libboost-all-dev
python3 -m pip install --user -r requirements.txt
```

### Compiling

```bash
mkdir build
cd build
cmake -DPYBIND11_PYTHON_VERSION=3.9 ..  # -DCMAKE_INSTALL_PREFIX=$HOME/.local/
```

**Note:** The ` -DPYBIND11_PYTHON_VERSION=3.9` may be left out if the current `python3` is the Python version you want the module installed under.
**Warning:** The same Python version specified in cmake must be used to invoke setup.py

### Installation

To install the viz3 Python module, run the following:

```bash
make install  # -j$(nproc); nproc not in MacOS
python3 ../setup.py install  # --prefix=...
```

### Developing

The `viz3` framework contains two parts: a 3D layout system, written in C++ and stored in `src/`, and a Python wrapper stored in `viz3/` that uses the 3D layout system in conjuction with a data querying system to produce a visualization. The C++ to Python bindings are stored in `src/bindings/`, the C++ [Pybind11](https://pybind11.readthedocs.io) library is used to generate these bindings.

```bash
make all
```

This should generate several outputs:

- `libviz3.a` The C++ library that can be linked against.

- `viz3/core.cpython-39-darwin.so` The Python shared library loaded when `import viz3.core` is done (this must be done in this directory).

In the end `viz3/` contains a complete Python-based viz3 library:

```
viz3/__init__.py
viz3/acache.py
viz3/bindings.py
viz3/colors.py
viz3/core.cpython-39-darwin.so
viz3/datagraph/__init__.py
viz3/datagraph/__pycache__
viz3/datagraph/influx.py
viz3/datagraph/pcp.py
viz3/datagraph/prometheus.py
viz3/datagraph/sqlite.py
viz3/datagraph/test.py
viz3/from_xml.py
viz3/lang.py
viz3/renderer/__init__.py
viz3/renderer/panda3d.py
viz3/renderer/web.py
viz3/transformation.py
viz3/tree.py
viz3/utils.py
viz3/visualize.py
```

where each module can be imported via something like `import viz3.datatree`.

**Note:** For development purposes, executing your Python scripts that use `viz3` in the root directory and importing like described above should work against your local version. Otherwise, the installed version will be used!

### Examples

The `examples/` folder contains example visualizations shown in the paper. Since viz3 is meant to be used against active database, a `examples/cache` directory within stores cached responses that are used with the `conf/viz3.yaml` configuration.

#### Running Examples

The following commands will automatically launch web visualizations. If a desktop visualization is preferred, the `--panda3d` flag can be provided within the `Makefile` with the `RENDERER` macro. Furthermore, if your `python3` version differs from the one specified with cmake, the `PYTHON` Makefile macro must be changed.

```bash
make machine_room_simple
# or
make motherboard
# or
make machine_room_full  # May take 15+ mins or more
# or
python3 viz-realtime-procs.py
```
