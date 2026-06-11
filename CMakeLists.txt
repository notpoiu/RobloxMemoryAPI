cmake_minimum_required(VERSION 3.15)

project(robloxmemoryapi_native LANGUAGES CXX)

find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(memory MODULE src/robloxmemoryapi/_native/memory.cpp)
target_compile_features(memory PRIVATE cxx_std_17)

if(WIN32)
    target_link_libraries(memory PRIVATE psapi)
endif()

install(TARGETS memory
    LIBRARY DESTINATION robloxmemoryapi/_native
    RUNTIME DESTINATION robloxmemoryapi/_native
)
