"""One-shot layout of the RM2 radio and the APS6404L PSRAM on Pi's RP2350B board.

Run once, after tools/update_pcb_from_sch.py, inside KiCad's Python:

    python3 tools/layout_rm2.py RP2350B-RM2.kicad_pcb

Pi's own placement and routing is left as it was. The only edits to Pi's copper are
where the schematic changed underneath it:

- U4 is now a 150 mil SOIC-8 under U3, so the back-side fan-out vias that sat where
  its pads now are get replaced by a new fan-out between the pad rows.
- PSRAM chip select moved from GPIO0 to GPIO47, so R11's GPIO0 stub comes off and a
  GPIO47 run (back layer) goes in.
- GPIO43-47 no longer go to J3, so Pi's runs to those pins are cut short: the radio
  lines turn into lanes beside J3, and GPIO47 ends at the via to R11.
- The JST debug connector J4 is gone (SWD/SWCLK are on J3), so its GND stubs come off
  and SWD/SWCLK, which ran through its pads, run straight on to J3.

The board is stretched 18 mm at the end away from USB, like a Pico 2 W, and the RM2
sits between the headers there with its antenna end at the new bottom edge. The
bottom mounting holes move to the new end. J2/J3 are single-row headers on Pi's signal
columns, with 3V3 and GND pins at their ends. A rule area across the full board width
keeps copper off both layers under the antenna, and every RM2 ground pad gets its own
via to the back ground plane. The gSPI lines run down the top layer between J3 and the
board edge, where Pi's outer GND column used to be.
"""
import sys

import pcbnew

B = pcbnew.LoadBoard(sys.argv[1])
MM = pcbnew.FromMM
F, BK = pcbnew.F_Cu, pcbnew.B_Cu


def P(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def net(name):
    n = B.GetNetInfo().GetNetItem(name)
    assert n is not None, name
    return n


FPS = {f.GetReference(): f for f in B.GetFootprints()}


def fp(ref):
    return FPS[ref]


def track(netname, layer, *pts, w=0.15):
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(B)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(MM(w))
        t.SetLayer(layer)
        t.SetNet(net(netname))
        B.Add(t)


def via(netname, x, y):
    v = pcbnew.PCB_VIA(B)
    v.SetPosition(P(x, y))
    v.SetWidth(MM(0.6))
    v.SetDrill(MM(0.25))
    v.SetNet(net(netname))
    B.Add(v)


def near(a, b, tol=0.02):
    return abs(pcbnew.ToMM(a[0]) - b[0]) < tol and abs(pcbnew.ToMM(a[1]) - b[1]) < tol


def remove_tracks(netname, layer, *segs):
    """Remove track segments by endpoints (either direction)."""
    for a, b in segs:
        hit = [t for t in B.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == netname
               and t.GetLayer() == layer
               and ((near((t.GetStart().x, t.GetStart().y), a) and near((t.GetEnd().x, t.GetEnd().y), b))
                    or (near((t.GetStart().x, t.GetStart().y), b) and near((t.GetEnd().x, t.GetEnd().y), a)))]
        assert len(hit) == 1, (netname, a, b, len(hit))
        B.Delete(hit[0])


def remove_via(netname, x, y):
    hit = [t for t in B.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == netname
           and near((t.GetPosition().x, t.GetPosition().y), (x, y))]
    assert len(hit) == 1, (netname, x, y)
    B.Delete(hit[0])


def place(ref, x, y, rot=None):
    f = fp(ref)
    f.SetPosition(P(x, y))
    if rot is not None:
        f.SetOrientationDegrees(rot)
    return f


def zone_like(proto_net, proto_layer, layer, netname, pts, priority, name='', solid=False):
    proto = [z for z in B.Zones() if not z.GetIsRuleArea() and z.GetNetname() == proto_net
             and z.GetLayer() == proto_layer][0]
    z = pcbnew.ZONE(B)
    z.SetLayer(layer)
    z.SetNet(net(netname))
    z.SetAssignedPriority(priority)
    z.SetLocalClearance(proto.GetLocalClearance())
    z.SetMinThickness(proto.GetMinThickness())
    z.SetThermalReliefGap(proto.GetThermalReliefGap())
    z.SetThermalReliefSpokeWidth(proto.GetThermalReliefSpokeWidth())
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if solid else proto.GetPadConnection())
    z.SetIslandRemovalMode(proto.GetIslandRemovalMode())
    z.SetZoneName(name)
    z.Outline().NewOutline()
    for x, y in pts:
        z.Outline().Append(MM(x), MM(y))
    B.Add(z)
    return z


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ---------------------------------------------------------------- board outline
# Stretch the board 18 mm at the end away from USB; the width stays 52 mm.
BOT = 159.5                          # new bottom edge (was 141.5)
removed = 0
for d in list(B.GetDrawings()):
    if d.GetLayer() != pcbnew.Edge_Cuts:
        continue
    s = (round(pcbnew.ToMM(d.GetStart().x), 3), round(pcbnew.ToMM(d.GetStart().y), 3))
    e = (round(pcbnew.ToMM(d.GetEnd().x), 3), round(pcbnew.ToMM(d.GetEnd().y), 3))
    if max(s[1], e[1]) > 100:        # both sides and the bottom edge with its corners
        B.Delete(d)
        removed += 1
assert removed == 5, removed
edge_w = MM(0.1)


def seg(a, b):
    s = pcbnew.PCB_SHAPE(B, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a))
    s.SetEnd(P(*b))
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(edge_w)
    B.Add(s)


def arc(a, m, b):
    s = pcbnew.PCB_SHAPE(B, pcbnew.SHAPE_T_ARC)
    s.SetArcGeometry(P(*a), P(*m), P(*b))
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(edge_w)
    B.Add(s)


R2 = 0.7071067811865476
seg((74, 73), (74, BOT - 3))
arc((74, BOT - 3), (77 - 3 * R2, BOT - 3 + 3 * R2), (77, BOT))
seg((77, BOT), (123, BOT))
arc((123, BOT), (123 + 3 * R2, BOT - 3 + 3 * R2), (126, BOT - 3))
seg((126, BOT - 3), (126, 73))

# ---------------------------------------------------------------- RM2 and friends
# Between the headers at the far end, antenna end (pins 1/21) toward the new bottom edge.
# The module's top edge stays below Pi's "Minimal Design Example R4" silkscreen line.
CX, CY = 100.0, 151.0
u5 = place('U5', CX, CY, 180)
ref = u5.GetField('Reference')
ref.SetPosition(P(CX, CY + 1.5))
ref.SetLayer(pcbnew.F_Fab)
place('R14', 109.3, 146.05, 180)     # GPIO45 -> DO, 470R
place('R15', 112.0, 146.4, 90)       # GPIO45 -> IRQ, 10k
place('R16', 104.9, 140.9, 0)        # WL_GPIO0 -> LED, 1k
place('D1', 107.6, 140.9, 180)
place('C25', 95.5, 140.9, 90)        # VDDIO 100n
place('C24', 91.3, 147.4, -90)       # VIN 100n
place('C23', 89.2, 147.5, -90)       # VIN 10u
for r in ('R14', 'R15', 'R16', 'D1', 'C23', 'C24', 'C25'):
    fp(r).GetField('Reference').SetVisible(False)   # no room for refdes silk; Fab layer keeps them

pad = {p.GetNumber(): (round(pcbnew.ToMM(p.GetPosition().x), 3), round(pcbnew.ToMM(p.GetPosition().y), 3))
       for p in u5.Pads()}
assert pad['1'] == (106.75, 153.55) and pad['9'] == (103.0, 143.25) and pad['16'] == (93.25, 146.05), pad

G45, G46, G44, G43 = '/GPIO45_ADC5', '/GPIO46_ADC6', '/GPIO44_ADC4', '/GPIO43_ADC3'
# J3's top five pins (GPIO47-43 on Pi's board) are 3V3/GND now. Pi's diagonals to them stop
# short, slip between the J3 pins, and run down four lanes between J3 and the board edge,
# where the outer GND column used to be.
L_WL, L_CS, L_DI, L_SCK = 122.9, 123.6, 124.3, 125.0
for n, (x0, y0), gap_y in ((G46, (113.2, 84.93), 77.81), (G45, (114.2, 86.47), 80.35),
                           (G44, (115.2, 88.01), 82.89), (G43, (116.2, 89.55), 85.43)):
    remove_tracks(n, F, ((x0, y0), (121.59, gap_y - 1.27)))
    track(n, F, (x0, y0), (120.32, gap_y))       # same 45 degree line, ending between two pins
track(G46, F, (120.32, 77.81), (L_SCK, 77.81), (L_SCK, pad['3'][1]), pad['3'])
track(G45, F, (120.32, 80.35), (L_DI, 80.35), (L_DI, pad['5'][1]), pad['5'])
track(G44, F, (120.32, 82.89), (L_CS, 82.89), (L_CS, 144.4), (109.4, 144.4), (109.4, 139.0),
      (103.0, 139.0), pad['9'])
track(G43, F, (120.32, 85.43), (L_WL, 85.43), (L_WL, 143.9), (110.2, 143.9), (110.2, 138.2),
      (98.5, 138.2), pad['12'])
track(G43, F, pad['12'], pad['13'])                                 # BT_ON
# DO through R14, IRQ through R15 (one short hop under CS on the back layer)
track(G45, F, (109.81, 146.05), (109.81, 147.55))                   # R14.1
track('Net-(U5-DO)', F, (108.79, 146.05), pad['6'])
track(G45, F, (112.0, 146.91), (112.0, 147.55))                     # R15.1
track('Net-(U5-~{IRQ})', F, (112.0, 145.89), (113.0, 145.89))
via('Net-(U5-~{IRQ})', 113.0, 145.89)
track('Net-(U5-~{IRQ})', BK, (113.0, 145.89), (108.11, 141.0), (101.5, 141.0))
via('Net-(U5-~{IRQ})', 101.5, 141.0)
track('Net-(U5-~{IRQ})', F, (101.5, 141.0), pad['10'])
# LED: pad 8 -> R16 -> D1 -> GND
track('Net-(U5-GPIO0)', F, (104.39, 140.9), (104.39, 143.25))
track('Net-(D1-A)', F, (105.41, 140.9), (106.81, 140.9))
track('GND', F, (108.39, 140.9), (108.4, 139.95))
via('GND', 108.4, 139.95)

# 3V3: VDDIO and VIN with their decoupling; the top-layer +3V3 pour joins them to Pi's
track('+3V3', F, (95.5, 141.38), pad['14'], w=0.4)                  # C25.1
track('+3V3', F, pad['16'], (89.2, 146.05), (89.2, 146.55), w=0.4)  # VIN -> C24, C23
track('+3V3', F, (91.3, 146.05), (91.3, 146.92), w=0.4)
for (x, y), (vx, vy) in (((95.5, 140.42), (95.5, 139.5)), ((91.3, 147.88), (91.3, 148.9)),
                         ((89.2, 148.45), (89.2, 149.7))):
    track('GND', F, (x, y), (vx, vy), w=0.3)
    via('GND', vx, vy)

# a short via to the back ground plane at every RM2 ground pad
for n, v in (('11', (100.0, 140.9)), ('7', (108.6, 144.55)), ('4', (108.6, 149.05)),
             ('1', (108.6, 153.55)), ('15', (91.4, 144.55)), ('21', (91.4, 153.55))):
    track('GND', F, pad[n], v, w=0.3)
    via('GND', *v)

# J2/J3 are single-row headers on Pi's inner (signal) columns; the outer GND columns are gone.
# J2: 3V3, GPIO0-24, GND, 3V3, GND.  J3: 3V3, 3V3, GND x3, GPIO42-25 (RUN/SWD/SWCLK as before), 3V3, GND.
place('J2', 78.41, 74.0, 0)
place('J3', 121.59, 74.0, 0)
# J3's 3V3 pins: the top two join the +3V3 pour above J3; the bottom one sits between Pi's GPIO25
# pin and the WL_ON lane, so it gets a track into the pour and a solid connection
track('+3V3', F, (121.59, 76.54), (121.59, 74.0), (121.59, 71.6), w=0.4)
track('+3V3', F, (121.59, 140.04), (119.6, 140.04), w=0.4)
for p in fp('J3').Pads():
    if p.GetNumber() == '27':
        p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)


def silk_label(text, x, y, just):                    # in the style of Pi's GPxx labels
    t = pcbnew.PCB_TEXT(B)
    t.SetText(text)
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(MM(0.9), MM(0.9)))
    t.SetTextThickness(MM(0.1))
    t.SetHorizJustify(just)
    t.SetPosition(P(x, y))
    B.Add(t)


LEFT, RIGHT = pcbnew.GR_TEXT_H_ALIGN_LEFT, pcbnew.GR_TEXT_H_ALIGN_RIGHT
for y, text in ((140.04, 'GND'), (142.58, '3V3'), (145.12, 'GND')):
    silk_label(text, 80.315, y, LEFT)
for y, text in ((140.04, '3V3'), (142.58, 'GND')):
    silk_label(text, 119.685, y, RIGHT)
# Pi's silkscreen: J3's top labels become the power pins, ADC now ends at 42, no outer row
relabel = {'GP47': '3V3', 'GP46': '3V3', 'GP45': 'GND', 'GP44': 'GND', 'GP43': 'GND'}
for d in list(B.GetDrawings()):
    if d.GetClass() != 'PCB_TEXT' or d.GetLayer() != pcbnew.F_SilkS:
        continue
    if d.GetText() in relabel:
        d.SetText(relabel[d.GetText()])
    elif d.GetText() == 'ADC 40-47':
        d.SetText('ADC 40-42')
        d.SetPosition(P(114.4, 89.24))               # centred on GP40-42 (J3 pins 6-8)
    elif d.GetText() == 'Outer Row GND':
        B.Delete(d)

# the bottom mounting holes move to the new end, in line with the top pair (4 mm from the edge)
place('MH3', 113.97, BOT - 4)
place('MH4', 86.03, BOT - 4)

# zones for the stretched end: back GND plane, +3V3 on top, GND on top under the module
ANT = CY + 3.3                       # module's antenna line
zone_like('GND', BK, BK, 'GND', rect(73.5, 140.0, 126.5, BOT + 0.5), 11, 'RM2 end GND')
zone_like('+3V3', F, F, '+3V3', rect(73.5, 140.0, 126.5, BOT + 0.5), 10, 'RM2 end 3V3')
zone_like('GND', BK, F, 'GND', rect(92.3, 142.3, 107.7, ANT), 20, 'RM2 GND under module', solid=True)

# antenna strip: no copper on any layer from the module's antenna line to the board edge,
# across the full board width
ka = pcbnew.ZONE(B)
ka.SetIsRuleArea(True)
ka.SetLayerSet(pcbnew.LSET.AllCuMask())
ka.SetDoNotAllowTracks(True)
ka.SetDoNotAllowVias(True)
ka.SetDoNotAllowPads(False)          # the NPTH mounting holes sit here
ka.SetDoNotAllowZoneFills(True)
ka.SetDoNotAllowFootprints(False)
ka.SetZoneName('RM2 antenna strip: no copper')
ka.Outline().NewOutline()
for x, y in rect(73.5, ANT, 126.5, BOT + 0.5):
    ka.Outline().Append(MM(x), MM(y))
B.Add(ka)

# ---------------------------------------------------------------- U4: 150 mil SOIC under U3
SD0, SD1, SD2, SD3, SCK = '/QSPI_SD0', '/QSPI_SD1', '/QSPI_SD2', '/QSPI_SD3', '/QSPI_SCLK'
for n, x, y in ((SD1, 90.7, 86.9), (SD2, 90.7, 88.2), (SD0, 95.3, 88.8), (SCK, 95.3, 87.5), (SD3, 95.3, 86.2)):
    remove_via(n, x, y)
for t in [t for t in B.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetLayer() == BK
          and t.GetNetname() in (SD0, SD1, SD2, SD3, SCK)]:
    B.Delete(t)
remove_tracks(SD1, F, ((90.7, 86.9), (90.36, 86.56)), ((90.36, 86.56), (89.4, 86.56)))
remove_tracks(SD0, F, ((95.61, 89.11), (95.3, 88.8)), ((96.6, 89.11), (95.61, 89.11)))
remove_tracks(SCK, F, ((95.64, 87.83), (96.6, 87.83)), ((95.3, 87.5), (95.64, 87.83)))
remove_tracks(SD3, F, ((95.3, 86.2), (95.67, 86.56)), ((95.67, 86.56), (96.6, 86.56)))
# U3 left -> U4 right: cross on top, via beside U4's pad
track(SD1, F, (89.4, 86.565), (93.9, 86.565))
via(SD1, 93.9, 86.565)
track(SD1, BK, (93.9, 86.565), (95.475, 86.565))
track(SD2, F, (90.33, 87.83), (93.9, 87.835))
via(SD2, 93.9, 87.835)
track(SD2, BK, (93.9, 87.835), (95.475, 87.835))
# U3 right -> U4 left: cross on top between those vias, via beside U4's pad
track(SD3, F, (96.6, 86.565), (95.965, 87.2), (92.1, 87.2))
via(SD3, 92.1, 87.2)
track(SD3, BK, (92.1, 87.2), (91.465, 86.565), (90.525, 86.565))
track(SCK, F, (96.6, 87.835), (95.965, 88.47), (92.1, 88.47))
via(SCK, 92.1, 88.47)
track(SCK, BK, (92.1, 88.47), (91.465, 87.835), (90.525, 87.835))
via(SD0, 96.6, 90.5)                 # on U3's existing SD0 run
track(SD0, BK, (96.6, 90.5), (91.92, 90.5), (90.525, 89.105))
track('+3V3', BK, (89.4, 85.3), (90.525, 85.295))
# chip select: Pi's FLASH2_SS run now carries PSRAM_CS; trim its end to the new pad
for t in [t for t in B.GetTracks() if t.GetNetname() == '/FLASH2_SS']:
    t.SetNet(net('/PSRAM_CS'))
remove_tracks('/PSRAM_CS', BK, ((93.89, 85.3), (96.6, 85.3)))
track('/PSRAM_CS', BK, (93.89, 85.3), (95.475, 85.295))

# ---------------------------------------------------------------- J4 (debug connector) removed
# SWD/SWCLK are on J3, so the JST debug connector is gone. Its GND stubs and vias go with it,
# and SWD/SWCLK, which Pi ran through J4's pads, run straight on to J3.
for a, b in (((110.9, 125.8), (110.9, 127.2)), ((110.875, 129.675), (110.9, 129.7)),
             ((113.2, 129.675), (110.925, 129.675)), ((108.6, 129.675), (110.875, 129.675)),
             ((110.925, 129.675), (110.9, 129.7))):
    remove_tracks('GND', F, (a, b))
remove_via('GND', 110.9, 127.2)
remove_via('GND', 110.9, 129.7)
remove_tracks('/SWD', F, ((105.1, 118.5), (111.9, 125.3)), ((111.9, 125.3), (111.9, 125.8)),
              ((111.9, 125.8), (120.05, 125.8)))
track('/SWD', F, (105.1, 118.5), (112.4, 125.8), (120.05, 125.8))
remove_tracks('/SWCLK', F, ((104.3, 119.8), (109.9, 125.4)), ((109.9, 125.4), (109.9, 125.8)),
              ((109.9, 125.8), (109.9, 127.4)), ((109.9, 127.4), (110.8, 128.3)),
              ((110.8, 128.3), (120.01, 128.3)))
track('/SWCLK', F, (104.3, 119.8), (112.8, 128.3), (120.01, 128.3))
for d in list(B.GetDrawings()):
    if d.GetClass() == 'PCB_TEXT' and d.GetText() == 'DEBUG':
        B.Delete(d)

# ---------------------------------------------------------------- R11: GPIO0 -> GPIO47
remove_tracks('/GPIO0', BK, ((90.9, 81.0), (93.02, 81.0)), ((93.02, 81.0), (93.1, 81.08)))
# GPIO47 no longer goes to J3: Pi's run is cut back to a via that takes it to R11
remove_tracks('/GPIO47_ADC7', F, ((112.2, 83.39), (121.59, 74.0)), ((112.2, 92.791231), (112.2, 83.39)))
track('/GPIO47_ADC7', F, (112.2, 92.791231), (112.2, 87.5))
via('/GPIO47_ADC7', 112.2, 87.5)
track('/GPIO47_ADC7', BK, (112.2, 87.5), (105.815, 81.115), (93.1, 81.115))

ni = B.GetNetInfo().GetNetItem('/FLASH2_SS')
if ni is not None:
    B.Delete(ni)

pcbnew.ZONE_FILLER(B).Fill(B.Zones())
B.Save(sys.argv[1])
