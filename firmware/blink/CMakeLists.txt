# Bring-up test for the RP2350B + RM2 board: blinks D1 (on the radio's WL_GPIO0),
# which only works if the RM2 powers up and talks over gSPI on GPIO 43-46.
# Build: PICO_SDK_PATH=/path/to/pico-sdk cmake -S . -B build -G Ninja && ninja -C build
cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD rp2350b_rm2)
set(PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/../boards)

include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(rm2_blink C CXX ASM)
pico_sdk_init()

add_executable(rm2_blink main.c)
target_link_libraries(rm2_blink pico_stdlib pico_cyw43_arch_none)
pico_enable_stdio_usb(rm2_blink 1)
pico_enable_stdio_uart(rm2_blink 1)
pico_add_extra_outputs(rm2_blink)
