# PSRAM heap (psram_malloc / psram_free) for pico-sdk 2.3.0+. Use from a project with:
#   add_subdirectory(path/to/psram_alloc psram_alloc)
#   target_link_libraries(my_app psram_alloc)
add_library(psram_alloc INTERFACE)
target_sources(psram_alloc INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/psram_alloc.c
    ${CMAKE_CURRENT_LIST_DIR}/tlsf/tlsf.c)
target_include_directories(psram_alloc INTERFACE ${CMAKE_CURRENT_LIST_DIR})
target_link_libraries(psram_alloc INTERFACE hardware_psram pico_sync)
