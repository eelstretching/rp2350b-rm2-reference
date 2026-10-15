# RP2350B + RM2

Raspberry Pi's RP2350B minimal design (RPI-RP2350B-MINIMAL R4-S1, KiCad 10) with two additions:

- the **RM2** Wi-Fi/Bluetooth module (CYW43439) on **GPIO 43-46**
- the **8 MB APS6404L PSRAM** fitted on the second QSPI chip select, moved from GPIO0 to **GPIO47**

That leaves **GPIO 0-42 free and in order** on the J2/J3 headers, instead of the Pico 2 W's gap
at 23/24/25/29.

Status: **schematic done, layout not started.** The `.kicad_pcb` is still Pi's original board, so
it has no RM2 and the old U4 footprint (see "Layout to do").

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
| `RP2350B-RM2.kicad_pcb` | Raspberry Pi's original R4 layout, untouched |
| `rp2350b_rm2.kicad_sym`, `rp2350b_rm2.pretty/RPi_RM2.kicad_mod` | RM2 symbol and footprint (project libraries, already in `sym-lib-table` / `fp-lib-table`) |
| `bom-jlcpcb.csv` | BOM with LCSC numbers |
| `firmware/boards/rp2350b_rm2.h` | pico-sdk board header (CYW43 pins, 16 MB flash, 8 MB PSRAM on GPIO47) |
| `firmware/blink/` | bring-up test: blinks D1 through the radio, so it proves the RM2 is alive |
| `tools/kisch.py`, `tools/kirender.py` | netlist dump/check and rough PNG preview of a schematic, no KiCad needed |
| `tools/rm2_footprint.py` | generator for the RM2 footprint |
| `docs/*.png` | rough schematic previews (full sheet, radio, PSRAM) |

## BOM / JLCPCB

Every part has an LCSC number except these three:

- **U5 RM2**: not stocked at LCSC. Buy Raspberry Pi SC1169 (Pimoroni, The Pi Hut, Mouser) and
  hand-solder it. The footprint's pads run 0.5 mm past the module edge to make that easier.
- **SW1/SW2** (Wurth 434133025816): not at LCSC. Use JLC global sourcing or hand-solder, or swap
  in an LCSC tact switch and change the footprint.
- **J2/J3** 2x26 headers: through-hole, hand-solder.

Passives were swapped from Pi's Murata/Yageo parts to JLC basic equivalents with the same value,
size and dielectric. The 100n parts are 16 V instead of 25 V, which is fine on 3.3 V.

## Layout to do

1. Open the project and run **Tools > Update PCB from Schematic**. That adds U5, R14-R16, C23-C25
   and D1, and swaps U4 to `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`. The APS6404L is a 150 mil
   SOP-8, and Pi's footprint was the 208 mil SOIC for a second W25Q flash.
2. Put the RM2 at a board edge with the antenna end (above pins 1 and 21) toward the edge. The
   footprint carries a copper keep-out over the antenna. Give it solid ground under the rest and
   short ground connections.
3. Keep R14/R15 close to the RM2, and the gSPI traces to GPIO 43-46 short.
4. The board outline will need to grow, or move the headers, to fit the module.

## Verification so far

- `python3 tools/kisch.py RP2350B-RM2.kicad_sch` reports no dangling pins and no multi-named nets.
  A net-by-net diff against Pi's original shows only the intended changes (RM2 nets, PSRAM CS
  GPIO0 to GPIO47, new decoupling).
- The RM2 pad positions match SparkFun's independently drawn RM2 footprint (XRP Controller) at
  every pad's inner edge.
- `firmware/blink` compiles against pico-sdk 2.3.0 with this board header.
- Not yet opened in KiCad itself: run ERC once you load it.

## License

Raspberry Pi's design is MIT (see `LICENSE-RaspberryPi.txt`); the additions here are MIT too.
The board header is BSD-3-Clause, derived from pico-sdk board headers.
