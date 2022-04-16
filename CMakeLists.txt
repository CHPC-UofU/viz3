project(viz3 LANGUAGES CXX)
cmake_minimum_required(VERSION 3.4)
set(CMAKE_CXX_STANDARD 17)

# Find boost QVM header library
find_package(Boost REQUIRED)
include_directories(SYSTEM ${Boost_INCLUDE_DIRS})

set(CMAKE_INSTALL_RPATH "${CMAKE_INSTALL_PREFIX}/lib")

# Find PMP-Library (https://www.pmp-library.org/). Git is used, since the
# latest release (1.2.1) doesn't contain installation code in their CMakeLists.txt
set(PMP_BUILD_APPS OFF)
set(PMP_BUILD_EXAMPLES OFF)
set(PMP_BUILD_TESTS OFF)
set(PMP_BUILD_DOCS OFF)
set(PMP_BUILD_VIS OFF)
add_subdirectory(lib/pmp/git)

# Build libviz3.a
add_library(libviz3 SHARED src/bounds.cpp src/bounds.hpp src/box.cpp src/box.hpp src/color.cpp src/color.hpp src/coords.cpp src/coords.hpp src/element.hpp src/event.cpp src/event.hpp src/feature.cpp src/feature.hpp src/geometry.cpp src/geometry.hpp src/layout.cpp src/layout.hpp src/node.cpp src/node.hpp src/path.cpp src/path.hpp src/pmp.cpp src/pmp.hpp src/render.cpp src/render.hpp src/rotation.cpp src/rotation.hpp src/transaction.hpp src/value.cpp src/value.hpp src/value_types.cpp src/value_types.hpp src/viz3.cpp src/viz3.hpp)
# Make libviz3, not liblibviz3; viz3 alone conflicts with the project name
set_target_properties(libviz3 PROPERTIES OUTPUT_NAME viz3)
target_compile_options(libviz3 PRIVATE -Wall -Wundef -Wpedantic -Wextra -Woverloaded-virtual -Wsuggest-override)
set_target_properties(libviz3 PROPERTIES POSITION_INDEPENDENT_CODE ON)  # required for Python module
# CMake strips the rpath when installing by default. This is terrible for us,
# since our Python .so library is installed elsewhere (where
# $CMAKE_INSTALL_PREFIX is, not wherever setup.py installs to). So stop CMake.
# https://stackoverflow.com/questions/32469953/why-is-cmake-designed-so-that-it-removes-runtime-path-when-installing
# https://gitlab.kitware.com/cmake/community/-/wikis/doc/cmake/RPATH-handling
# https://developer.apple.com/library/archive/documentation/DeveloperTools/Conceptual/DynamicLibraries/100-Articles/RunpathDependentLibraries.html
set_target_properties(libviz3 PROPERTIES INSTALL_RPATH_USE_LINK_PATH TRUE)
target_link_libraries(libviz3 PRIVATE pmp)
target_include_directories(libviz3 SYSTEM PRIVATE lib/pmp/git/src)
target_include_directories(libviz3 SYSTEM PRIVATE lib/pmp/git/external/eigen)
target_include_directories(libviz3 SYSTEM PRIVATE lib/pmp/git/external/eigen)

# Build core.cpython-*.so
# Use cmake -DPYBIND11_PYTHON_VERSION=3.9 or -DPYTHON_EXECUTABLE=$(command -v python3) to
# specify Python version (defaults to latest installed)
add_subdirectory(lib/pybind11/latest)
pybind11_add_module(core SHARED src/bindings/bindings.cpp)
set_target_properties(core PROPERTIES INSTALL_RPATH_USE_LINK_PATH TRUE)
target_link_libraries(core PRIVATE libviz3 pmp)

# Install core library to viz3/ Python module. setup.py will then copy that
# along to wherever it puts its stuff
install(TARGETS libviz3 COMPONENT library LIBRARY DESTINATION lib)
install(TARGETS core COMPONENT python LIBRARY DESTINATION ${PROJECT_SOURCE_DIR}/viz3)

# libviz3 Tests
# If someone add_subdirectory() our repository, don't force our tests on them
# If you do want to develop viz3, use -DBUILD_TESTING=ON and build within this
# repository
if(CMAKE_PROJECT_NAME STREQUAL PROJECT_NAME AND BUILD_TESTING)
    add_subdirectory(tests)
endif()
