# RP2350B + RM2

Raspberry Pi's RP2350B minimal design (RPI-RP2350B-MINIMAL R4-S1, KiCad 10) with three additions:

- the **RM2** Wi-Fi/Bluetooth module (CYW43439) on **GPIO 43-46**
- the **8 MB APS6404L PSRAM** fitted on the second QSPI chip select, moved from GPIO0 to **GPIO47**
- **single-row headers**: J2/J3 are 1x29 / 1x28 rows with the GPIOs in order and **3V3 and GND
  pins at both ends**, in place of Pi's 2x26 headers with an all-GND outer row. That makes the
  board easy to use on perfboard, with 3.3 V on hand for level shifters and the like

That leaves **GPIO 0-42 free and in order** on the J2/J3 headers, instead of the Pico 2 W's gap
at 23/24/25/29.

Status: **schematic and layout done, DRC clean, not yet fabricated.** See "Layout" for what changed
on Pi's board.

![Front copper](docs/pcb-front.png)

## Pin map

| GPIO | Use |
|---|---|
| 0-42 | free, on J2/J3 (0/1 = default UART0) |
| 43 | RM2 WL_ON + BT_ON |
| 44 | RM2 gSPI CS |
| 45 | RM2 gSPI DATA: DI direct, DO through 470R (R14), IRQ through 10k (R15) |
| 46 | RM2 gSPI CLK |
| 47 | PSRAM chip select (XIP_SS_N[1]), 10k pull-up R13, 0R link R11 |

GPIO 43-47 aren't on the headers: they belong to the radio and the PSRAM.

The headers, from the USB end down:

| Header | Top | Middle | Bottom |
|---|---|---|---|
| J2 (left, 29 pins) | 3V3 | GP0-GP24 | GND, 3V3, GND |
| J3 (right, 28 pins) | 3V3, 3V3, GND, GND, GND | GP42-GP28, RUN, SWD, SWCLK, GP27-GP25 | 3V3, GND |

The radio circuit is the Pico 2 W's (and the RM2 datasheet's) on different pins:

- VIN and VDDIO go to +3V3, with 10u + 2x 100n local decoupling.
- WL_GPIO0 drives a green LED (D1) through 1k. That's the SDK's `CYW43_WL_GPIO_LED_PIN`.
- WL_GPIO1, WL_GPIO2 and the NC pins aren't connected.

The cyw43 driver takes any pins from the board header, so nothing else changes in firmware. On the
RP2350B a PIO block reaches either GPIO 0-31 or 16-47. The radio's PIO therefore sits in the
16-47 window, which means LED output PIOs for GPIO 0-15 must use a different PIO block.

## Using it on perfboard

J2 and J3 are single rows on the 0.1" grid, 1.7" (17 holes) apart, so the module drops straight
into perfboard, and every pin has free holes beside it.

- **Socket it and wire on the underside.** Put female headers on the perfboard and plug the module
  in, then wire underneath with thin insulated wire (Kynar or wire-wrap). The area under the module
  is free routing space. Socketing also gives the parts on the module's underside room: U4 (the
  PSRAM, 1.75 mm tall SOIC), R11, R13 and C22. Plain header pins pushed fully home leave only
  about 2.5 mm.
- **Keep the antenna end clear.** Let the RM2 end overhang the perfboard edge, or keep that area
  free of wires, copper and ground. Anything conductive close under the antenna detunes it.

Two traps:

- **Stripboard (Veroboard):** run the strips outward, perpendicular to the headers, so each pin
  gets its own strip. Then cut every strip somewhere between the two headers. Otherwise a strip
  runs under the module and joins each J2 pin to the J3 pin in the same row: GPIO0 to 3V3,
  GPIO1 to GND, and at the bottom 3V3 straight to GND.
- **Solderless breadboard:** the 1.7" span between the rows is too wide to straddle a standard
  breadboard.

## PSRAM in your own code

With pico-sdk 2.3.0 or later, linking `hardware_psram` brings the PSRAM up at boot. It reads
`PICO_PSRAM_CS_PIN` and `PICO_PSRAM_SIZE_BYTES`, which the board header already sets. The PSRAM then
appears as ordinary memory at 0x11000000.

- **Static data:** `__uninitialized_psram("name")` (or `__in_psram("name")` for initialised data)
  places a variable or array in PSRAM.
- **Dynamic allocation:** `firmware/psram_alloc` adds `psram_malloc`, `psram_calloc`,
  `psram_realloc`, `psram_memalign` and `psram_free`, plus `psram_heap_stats()`. These work like
  malloc (8-byte aligned, safe from both cores, not from interrupt handlers) but allocate from the
  PSRAM left after any PSRAM variables. The SDK's own `malloc` stays in the faster on-chip SRAM.
  It's a TLSF allocator with its control block in SRAM. To use it:

  ```cmake
  add_subdirectory(path/to/firmware/psram_alloc psram_alloc)
  target_link_libraries(my_app psram_alloc)
  ```

PSRAM is slower than SRAM, so use it for big, mostly-streamed data (frame and pixel buffers, audio,
network buffers). Keep stacks and hot data in SRAM. `firmware/psram_test` prints the throughput, and
is the first thing to run on a new board to check U4.

## Files

| Path | What |
|---|---|
| `RP2350B-RM2.kicad_sch` | schematic (single sheet, A3) |
| `RP2350B-RM2.kicad_pcb` | Pi's R4 layout, 18 mm longer, plus the RM2 and the PSRAM (see "Layout") |
| `rp2350b_rm2.kicad_sym`, `rp2350b_rm2.pretty/RPi_RM2.kicad_mod` | RM2 symbol and footprint (project libraries, already in `sym-lib-table` / `fp-lib-table`) |
| `bom-jlcpcb.csv` | BOM with LCSC numbers |
| `firmware/boards/rp2350b_rm2.h` | pico-sdk board header (CYW43 pins, 16 MB flash, 8 MB PSRAM on GPIO47) |
| `firmware/blink/` | bring-up test: blinks D1 through the radio, so it proves the RM2 is alive |
| `firmware/psram_test/` | bring-up test for the PSRAM: tests all 8 MB, measures throughput, exercises the heap |
| `firmware/psram_alloc/` | `psram_malloc()` / `psram_free()`: a heap in PSRAM for your own projects (TLSF, vendored) |
| `tools/kisch.py`, `tools/kirender.py` | netlist dump/check and rough PNG preview of a schematic, no KiCad needed |
| `tools/rm2_footprint.py` | generator for the RM2 footprint |
| `tools/update_pcb_from_sch.py`, `tools/layout_rm2.py` | the scripted Update PCB from Schematic and RM2/PSRAM layout pass that produced the board (run once, in KiCad's Python; kept for reference) |
| `docs/schematic-*.png` | rough schematic previews (full sheet, radio, PSRAM) |
| `docs/pcb-front.png`, `docs/pcb-back.png` | board renders (front copper and silk; back copper, mirrored) |

## BOM / JLCPCB

Every part has an LCSC number except these three:

- **U5 RM2**: not stocked at LCSC. Buy Raspberry Pi SC1169 (Pimoroni, The Pi Hut, Mouser) and
  hand-solder it. The footprint's pads run 0.5 mm past the module edge to make that easier.
- **SW1/SW2** (Wurth 434133025816): not at LCSC. Use JLC global sourcing or hand-solder, or swap
  in an LCSC tact switch and change the footprint.
- **J2/J3** 1x29 and 1x28 2.54 mm headers: through-hole, hand-solder (or socket, see "Using it on
  perfboard").

Passives were swapped from Pi's Murata/Yageo parts to JLC basic equivalents with the same value,
size and dielectric. The 100n parts are 16 V instead of 25 V, which is fine on 3.3 V.

## Layout

The board is Pi's R4 layout with **Update PCB from Schematic** applied, and the areas below added
or changed. Every Pi footprint stays where it was apart from the bottom mounting holes (MH3, MH4)
and the headers (J2, J3), which are now single rows on Pi's signal columns. Pi's JST debug
connector (J4) is gone, since SWD and SWCLK are on J3. Pi's tracks are untouched apart from the U4
fan-out, the R11 stub, the last stretch of GPIO43-47's runs to J3, and SWD/SWCLK where they used to
pass through J4.

**RM2 end.** The board is 18 mm longer (89.5 x 52 mm), and the extra length is at the end away from
USB, as on the Pico 2 W. The headers stay on both long edges. The RM2 (U5) sits between them,
centred, with its antenna end (pins 1 and 21) at the new bottom edge. The module's top edge clears
Pi's "Minimal Design Example R4" silkscreen line.

- Antenna: a rule area across the full board width, from the module's antenna line to the bottom
  edge, blocks copper, tracks and vias on both layers. That covers the footprint's own keep-out plus
  the copper on either side of it.
- Ground: there's a solid back-layer GND pour under the module and a top-layer GND pour under the
  module body. Each of the six RM2 GND pads (1, 4, 7, 11, 15, 21) has its own via to the back plane,
  within 2.4 mm of the pad centre.
- gSPI: GPIO43-46 run on top copper the whole way. Pi's runs to J3's top pins (now 3V3 and GND)
  stop just short of them and slip between those pins into four lanes beside J3, where Pi's outer
  GND column used to be, 0.7 mm apart. Below J3 they turn in toward the module. SCLK, DI and DO
  land on the module's right side, and CS and WL_ON wrap over its top.
- Length: the cost of the long-board layout is length. Each gSPI net runs 118-124 mm from U1
  (Pico 2 W: a few cm), about 30 mm of which is Pi's existing U1-to-J3 routing. That's still short
  next to a clock period at cyw43's default gSPI rate. But it's around the length where fast GPIO
  edges start to ring, and SCLK has no series resistor. If the radio misbehaves at bring-up, slow
  the bus with a higher `CYW43_PIO_CLOCK_DIV_INT` before suspecting anything else.
- R14 (DO, 470R) sits 1 mm from the DO pad, and R15 (IRQ, 10k) sits next to it on GPIO45. The IRQ
  line (host wake) takes the back layer for 12 mm to get from R15 to its pad under CS. It's the
  only radio signal off the top layer.
- Power: VIN has C24 (100n) and C23 (10u) next to it, and VDDIO has C25 (100n). Both sit in the
  top-layer +3V3 pour, which joins Pi's pour above the module. A sheet-resistance estimate of that
  copper puts U2's output to the RM2's VIN at about 15 mOhm, roughly 5 mV at a 300 mA transmit
  peak.
- D1 (WL_GPIO0 LED) and R16 sit just above the module's top-right corner.

The gSPI lanes run alongside J3's pins, so expect a little crosstalk from SCLK onto anything wired
to J3.

**Mounting holes.** MH3 and MH4 move from Pi's old bottom edge to the new end of the board, at the
same x as the top pair (86.03 and 113.97 mm) and 4 mm from the edge, again like the top pair. The
four holes keep Pi's rectangular pattern, now 27.94 x 81.5 mm. The top pair can't move into the
true corners because J2/J3 pin 1 is there. At the bottom, the holes flank the RM2's antenna
about 5 mm from its ends, as on the Pico 2 W. The antenna rule area allows them because they're
NPTH holes with no copper.

**Headers.** J2/J3 swap Pi's 2x26 Samtec headers for stock 1x29 / 1x28 2.54 mm headers on Pi's
inner (signal) columns, so every GPIO keeps its pad and Pi's routing to it. The outer GND column is
gone, and the top-layer +3V3 pour and the back GND plane fill its place.
- GND pins connect to the back plane.
- J3's top two 3V3 pins join the pour by U2 with a track, about 2 mOhm from U2's output.
- J3's bottom 3V3 pin sits between GPIO25's pin and the WL_ON lane, so it gets a track into the
  pour and a solid (not thermal) connection.
- J2's 3V3 pins take the pour around them, 9-17 mOhm from U2.

Pi's silkscreen labels for J3's top five pins now read 3V3 and GND, "ADC 40-47" reads "ADC 40-42",
and the "Outer Row GND" notes are gone. The new bottom pins get labels in the same style.

**U4 (PSRAM).** U4 swaps to `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm` at Pi's spot on the back, under
U3. Pi's back-side fan-out vias for the second flash sat where the 150 mil pads now are. They are
replaced by five new vias between the pad rows: SD1/SD2 cross on top and drop beside U4's right
column, SD3/SCLK cross on top between those vias and drop beside the left column, and SD0 drops from
U3's SD0 run and passes under U4 on the back. Pi's FLASH2_SS run from R11/R13 now carries PSRAM_CS.

**J4 (debug connector) removed.** SWD and SWCLK come out on J3 (pins 22 and 23, next to RUN on
pin 21), so Pi's JST debug connector is gone, along with its BOM line, its GND stubs and vias, and
the "DEBUG" silkscreen. Pi ran SWD and SWCLK through J4's pads on their way to J3. They now carry on
straight along the same 45-degree lines into their existing runs to J3.

**PSRAM CS on GPIO47.** R11's old GPIO0 stub is gone. GPIO47 now reaches R11 through a via on Pi's
GPIO47 run, which stops there instead of going on to J3, and a back-layer track. GPIO0's own route
to J2 is unchanged.

## Verification so far

- `python3 tools/kisch.py RP2350B-RM2.kicad_sch` reports no dangling pins and no multi-named nets.
  A net-by-net diff against Pi's original shows only the intended changes (RM2 nets, PSRAM CS
  GPIO0 to GPIO47, new decoupling).
- The RM2 pad positions match SparkFun's independently drawn RM2 footprint (XRP Controller) at
  every pad's inner edge.
- `firmware/blink` compiles against pico-sdk 2.3.0 with this board header.
- `firmware/psram_test` builds against pico-sdk 2.3.0 (arm-none-eabi-gcc 13.2), with no warnings
  from its own code under `-Wall -Wextra -Wshadow -Wconversion`. Its heap code (psram_alloc and the
  heap part of the test) passes on a host build in 32-bit mode, so TLSF's alignment behaves as on
  the RP2350, including under AddressSanitizer and UBSan. Not yet run on hardware.
- Checked headless with KiCad 10.0.6 (`kicad-cli` and pcbnew's Python), using the stock global
  library tables:
  - `kicad-cli pcb drc --schematic-parity --severity-all` reports 0 unconnected items and 0
    schematic-parity issues. The only remaining violations are 45 notes that the footprint library
    `RPI_COMPILED` isn't in the library table. Pi's original board has the same notes, because its
    footprints are embedded in the board.
  - `kicad-cli sch erc` reports 4 real items, in parts of the schematic this layout didn't touch: U2's
    two OUT pins tied together, U1 VREG_AVDD and #PWR16 "not driven" (power-flag nits), and one
    off-grid wire end. Everything else is the same library-table notes for Pi's libraries.
- Not yet opened in the KiCad GUI. After loading, refill zones (B) before plotting.

## License

Raspberry Pi's design is MIT (see `LICENSE-RaspberryPi.txt`); the additions here are MIT too.
The board header is BSD-3-Clause, derived from pico-sdk board headers.
