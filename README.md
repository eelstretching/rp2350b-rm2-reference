# RP2350B + RM2

Raspberry Pi's RP2350B minimal design (RPI-RP2350B-MINIMAL R4-S1, KiCad 10) with two additions:

- the **RM2** Wi-Fi/Bluetooth module (CYW43439) on **GPIO 43-46**
- the **8 MB APS6404L PSRAM** fitted on the second QSPI chip select, moved from GPIO0 to **GPIO47**

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

GPIO 43-47 are still wired to J3 as on Pi's board. Leave those header pins unloaded when the radio
and PSRAM are fitted.

The radio circuit is the Pico 2 W's (and the RM2 datasheet's) on different pins:

- VIN and VDDIO go to +3V3, with 10u + 2x 100n local decoupling.
- WL_GPIO0 drives a green LED (D1) through 1k. That's the SDK's `CYW43_WL_GPIO_LED_PIN`.
- WL_GPIO1, WL_GPIO2 and the NC pins aren't connected.

The cyw43 driver takes any pins from the board header, so nothing else changes in firmware. On the
RP2350B a PIO block reaches either GPIO 0-31 or 16-47. The radio's PIO therefore sits in the
16-47 window, which means LED output PIOs for GPIO 0-15 must use a different PIO block.

## Files

| Path | What |
|---|---|
| `RP2350B-RM2.kicad_sch` | schematic (single sheet, A3) |
| `RP2350B-RM2.kicad_pcb` | Pi's R4 layout plus the RM2 tab and the PSRAM (see "Layout") |
| `rp2350b_rm2.kicad_sym`, `rp2350b_rm2.pretty/RPi_RM2.kicad_mod` | RM2 symbol and footprint (project libraries, already in `sym-lib-table` / `fp-lib-table`) |
| `bom-jlcpcb.csv` | BOM with LCSC numbers |
| `firmware/boards/rp2350b_rm2.h` | pico-sdk board header (CYW43 pins, 16 MB flash, 8 MB PSRAM on GPIO47) |
| `firmware/blink/` | bring-up test: blinks D1 through the radio, so it proves the RM2 is alive |
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
- **J2/J3** 2x26 headers: through-hole, hand-solder.

Passives were swapped from Pi's Murata/Yageo parts to JLC basic equivalents with the same value,
size and dielectric. The 100n parts are 16 V instead of 25 V, which is fine on 3.3 V.

## Layout

The board is Pi's R4 layout with **Update PCB from Schematic** applied, and three areas added or
changed. Every Pi footprint stays where it was. Pi's tracks are untouched apart from the U4 fan-out and the R11 stub
described below.

**RM2 tab.** The outline grows by a 22.5 x 27.5 mm tab on the right edge, level with J3's top. The RM2
(U5) sits in the tab with its antenna end (pins 1 and 21) toward the tab's right edge. The radio
pins face J3's GPIO43-46. The board is 74.5 mm wide across the tab and keeps its 52 mm width below it.

- Antenna: a rule area across the whole antenna end of the tab, from the module's antenna line to the
  board edge, blocks copper, tracks and vias on both layers. That covers the footprint's own keep-out
  plus the copper around it.
- Ground: there's a solid back-layer GND pour under the module and a top-layer GND pour under the module
  body. Each of the six RM2 GND pads (1, 4, 7, 11, 15, 21) has its own via to the back plane, at most
  2 mm from the pad. J3's outer column (all GND) runs next to the tab and stitches the tab's plane to
  the main one.
- gSPI: GPIO43-46 leave J3's inner pins between the outer GND pins and run straight to the module, on
  top copper. Past J3, CS and WL_ON run about 12 mm. SCLK and DI run about 27 mm, because those
  pins are on the module's top side and their tracks go over it. From U1 the total is 38 mm (CS,
  WL_ON) and 55-57 mm (DI, SCLK), of which about 30 mm is Pi's existing U1-to-J3 routing. That's
  electrically short at cyw43's default gSPI clock (tens of MHz). Turning the antenna toward the top
  edge instead would shorten them, but would put the antenna about 2 mm from J3's metal pins.
  R14 (DO, 470R) sits 1.1 mm from the DO pad, and R15 (IRQ, 10k) sits next to the GPIO45 split.
  The IRQ line drops to the back layer for 4.7 mm to pass under CS. It's the only radio signal
  off the top layer.
- Power: VDDIO and VIN are tied by a 0.4 mm track, with C25 at VDDIO and C24/C23 at VIN. 3V3 comes
  from Pi's +3V3 pour strip that runs down the outside of J3. That strip is about 3 mm wide and is
  fed by Pi's wide 3V3 track at GP34.
- D1 (WL_GPIO0 LED) and R16 sit beside the module.

GPIO43-47 stay wired to J3's pins 1-9 as in the schematic. The radio traces pass through those header
pins, so leave them unloaded when the radio is fitted, as noted above.

**U4 (PSRAM).** U4 swaps to `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm` at Pi's spot on the back, under
U3. Pi's back-side fan-out vias for the second flash sat where the 150 mil pads now are. They are
replaced by five new vias between the pad rows: SD1/SD2 cross on top and drop beside U4's right
column, SD3/SCLK cross on top between those vias and drop beside the left column, and SD0 drops from
U3's SD0 run and passes under U4 on the back. Pi's FLASH2_SS run from R11/R13 now carries PSRAM_CS.

**PSRAM CS on GPIO47.** R11's old GPIO0 stub is gone. GPIO47 now reaches R11 through a via on Pi's
GPIO47 run to J3 and a back-layer track. GPIO0's own route to J2 is unchanged.

## Verification so far

- `python3 tools/kisch.py RP2350B-RM2.kicad_sch` reports no dangling pins and no multi-named nets.
  A net-by-net diff against Pi's original shows only the intended changes (RM2 nets, PSRAM CS
  GPIO0 to GPIO47, new decoupling).
- The RM2 pad positions match SparkFun's independently drawn RM2 footprint (XRP Controller) at
  every pad's inner edge.
- `firmware/blink` compiles against pico-sdk 2.3.0 with this board header.
- Checked headless with KiCad 10.0.6 (`kicad-cli` and pcbnew's Python), using the stock global
  library tables:
  - `kicad-cli pcb drc --schematic-parity --severity-all` reports 0 unconnected items and 0
    schematic-parity issues. The only remaining violations are 48 notes that the footprint library
    `RPI_COMPILED` isn't in the library table. Pi's original board has the same notes, because its
    footprints are embedded in the board.
  - `kicad-cli sch erc` reports 4 real items, in parts of the schematic this layout didn't touch: U2's
    two OUT pins tied together, U1 VREG_AVDD and #PWR16 "not driven" (power-flag nits), and one
    off-grid wire end. Everything else is the same library-table notes for Pi's libraries.
- Not yet opened in the KiCad GUI. After loading, refill zones (B) before plotting.

## License

Raspberry Pi's design is MIT (see `LICENSE-RaspberryPi.txt`); the additions here are MIT too.
The board header is BSD-3-Clause, derived from pico-sdk board headers.
