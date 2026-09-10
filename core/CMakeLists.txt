cmake_minimum_required(VERSION 3.15)
project(uniform_spectrum_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(pybind11 CONFIG REQUIRED)

add_library(spectrum_core STATIC
    src/graph6.cpp
)
target_include_directories(spectrum_core PUBLIC include)
# Needed for linking static library into a pybind11 shared module
set_target_properties(spectrum_core PROPERTIES POSITION_INDEPENDENT_CODE ON)

pybind11_add_module(uniform_spectrum_core src/bindings.cpp)
target_link_libraries(uniform_spectrum_core PRIVATE spectrum_core)
