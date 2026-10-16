# PSRAM bring-up test for the RP2350B + RM2 board: brings up the 8 MB APS6404L (U4, CS on
# GPIO47) through pico-sdk's hardware_psram, tests every byte, measures throughput and
# exercises the psram_alloc heap. Results on USB/UART stdio.
# Build (pico-sdk 2.3.0+): PICO_SDK_PATH=/path/to/pico-sdk cmake -S . -B build -G Ninja && ninja -C build
cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD rp2350b_rm2)
set(PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/../boards)

include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(psram_test C CXX ASM)
pico_sdk_init()

add_subdirectory(../psram_alloc psram_alloc)

add_executable(psram_test main.c)
target_link_libraries(psram_test pico_stdlib hardware_psram hardware_xip_cache psram_alloc)
pico_enable_stdio_usb(psram_test 1)
pico_enable_stdio_uart(psram_test 1)
pico_add_extra_outputs(psram_test)
