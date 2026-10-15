"""One-shot layout of the RM2 radio and the APS6404L PSRAM on Pi's RP2350B board.

Run once, after tools/update_pcb_from_sch.py, inside KiCad's Python:

    python3 tools/layout_rm2.py RP2350B-RM2.kicad_pcb

Pi's own placement and routing is left as it was. The only edits to Pi's copper are
where the schematic changed underneath it:

- U4 is now a 150 mil SOIC-8 under U3, so the back-side fan-out vias that sat where
  its pads now are get replaced by a new fan-out between the pad rows.
- PSRAM chip select moved from GPIO0 to GPIO47, so R11's GPIO0 stub comes off and a
  GPIO47 run (back layer) goes in.

The RM2 sits in a new tab on the right edge, next to J3's GPIO43-46 pins, with its
antenna end at the tab's right edge. A copper keep-out on both layers covers the
whole antenna strip of the tab, and every RM2 ground pad gets its own via to the
back ground plane.
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


def place(ref, x, y, rot, layer=F):
    f = fp(ref)
    f.SetPosition(P(x, y))
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
TAB_X, TAB_B = 148.5, 97.5          # tab right edge, tab bottom edge
removed = 0
for d in list(B.GetDrawings()):
    if d.GetLayer() != pcbnew.Edge_Cuts:
        continue
    s = (round(pcbnew.ToMM(d.GetStart().x), 3), round(pcbnew.ToMM(d.GetStart().y), 3))
    e = (round(pcbnew.ToMM(d.GetEnd().x), 3), round(pcbnew.ToMM(d.GetEnd().y), 3))
    if {s, e} in ({(77.0, 70.0), (123.0, 70.0)}, {(123.0, 70.0), (126.0, 73.0)}, {(126.0, 73.0), (126.0, 138.5)}):
        B.Delete(d)
        removed += 1
assert removed == 3, removed
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
seg((77, 70), (TAB_X - 3, 70))
arc((TAB_X - 3, 70), (TAB_X - 3 + 3 * R2, 73 - 3 * R2), (TAB_X, 73))
seg((TAB_X, 73), (TAB_X, TAB_B - 3))
arc((TAB_X, TAB_B - 3), (TAB_X - 3 + 3 * R2, TAB_B - 3 + 3 * R2), (TAB_X - 3, TAB_B))
seg((TAB_X - 3, TAB_B), (127, TAB_B))
arc((127, TAB_B), (127 - R2, TAB_B + 1 - R2), (126, TAB_B + 1))     # inside corner fillet
seg((126, TAB_B + 1), (126, 138.5))

# ---------------------------------------------------------------- RM2 and friends
CX, CY = 140.0, 84.0
u5 = place('U5', CX, CY, -90)        # antenna end (pins 1/21) toward +x
ref = u5.GetField('Reference')
ref.SetPosition(P(CX - 3, CY - 8.9))
ref.SetTextAngleDegrees(0)
place('R14', 135.05, 74.6, -90)      # GPIO45 -> DO, 470R
place('R15', 127.8, 77.81, 0)        # GPIO45 -> IRQ, 10k
place('R16', 129.8, 79.5, 180)       # WL_GPIO0 -> LED, 1k
place('D1', 127.2, 79.5, 0)
place('C25', 129.9, 88.5, 180)       # VDDIO 100n
place('C24', 136.8, 92.6, 0)         # VIN 100n
place('C23', 133.3, 95.2, 0)         # VIN 10u
for r in ('R14', 'R15', 'R16', 'D1', 'C23', 'C24', 'C25'):
    f = fp(r)
    f.GetField('Reference').SetVisible(False)   # no room for 0402 refdes silk; Fab layer keeps them

pad = {p.GetNumber(): (round(pcbnew.ToMM(p.GetPosition().x), 3), round(pcbnew.ToMM(p.GetPosition().y), 3))
       for p in u5.Pads()}
assert pad['1'] == (142.55, 77.25) and pad['8'] == (132.25, 79.5) and pad['16'] == (135.05, 90.75), pad

G45, G46, G44, G43 = '/GPIO45_ADC5', '/GPIO46_ADC6', '/GPIO44_ADC4', '/GPIO43_ADC3'
# SCLK: J3.3 -> outer gap -> over the top -> pad 3
track(G46, F, (121.59, 76.54), (122.86, 75.27), (125.6, 75.27), (125.6, 72.0), (139.55, 72.0), pad['3'])
# DI + DO (R14) + IRQ (R15): J3.5 -> outer gap
track(G45, F, (121.59, 79.08), (122.86, 77.81), (126.2, 77.81), (126.2, 73.0), (136.55, 73.0), pad['5'])
track(G45, F, (126.2, 77.81), (127.29, 77.81))                     # R15.1
track(G45, F, (135.05, 73.0), (135.05, 74.09))                     # R14.1
track('Net-(U5-DO)', F, (135.05, 75.11), pad['6'])
track('Net-(U5-~{IRQ})', F, (128.31, 77.81), (129.2, 77.81))
via('Net-(U5-~{IRQ})', 129.2, 77.81)
track('Net-(U5-~{IRQ})', BK, (129.2, 77.81), (129.2, 82.5))        # hop under CS
via('Net-(U5-~{IRQ})', 129.2, 82.5)
track('Net-(U5-~{IRQ})', F, (129.2, 82.5), pad['10'])
# CS: J3.7
track(G44, F, (121.59, 81.62), (122.86, 80.35), (125.6, 80.35), (126.25, 81.0), pad['9'])
# WL_ON + BT_ON: J3.9
track(G43, F, (121.59, 84.16), (122.93, 85.5), pad['12'])
track(G43, F, pad['12'], pad['13'])
# LED: pad 8 -> R16 -> D1 -> GND
track('Net-(U5-GPIO0)', F, (130.31, 79.5), pad['8'])
track('Net-(D1-A)', F, (127.99, 79.5), (129.29, 79.5))
track('GND', F, (125.6, 78.8), (126.3, 79.5), (126.41, 79.5))
via('GND', 125.6, 78.8)

# 3V3: VDDIO, VIN and their decoupling, fed from the +3V3 copper beside J3
track('+3V3', F, pad['14'], (130.38, 88.5), w=0.4)
track('+3V3', F, (130.9, 88.5), (130.9, 93.6), (135.05, 93.6), (135.05, 92.6), w=0.4)
track('+3V3', F, pad['16'], (135.05, 92.6), (136.32, 92.6), w=0.4)
track('+3V3', F, (132.35, 93.6), (132.35, 95.2), w=0.4)
track('+3V3', F, (130.9, 93.6), (126.5, 93.6), (125.95, 93.05), (125.3, 93.05), w=0.4)
# capacitor grounds
for (x, y), (vx, vy) in (((129.42, 88.5), (128.6, 88.5)), ((137.28, 92.6), (138.2, 92.6)),
                         ((134.25, 95.2), (135.4, 95.2))):
    track('GND', F, (x, y), (vx, vy), w=0.3)
    via('GND', vx, vy)

# a short via to the back ground plane at every RM2 ground pad
for n, v in (('1', (142.55, 75.4)), ('4', (138.05, 75.4)), ('7', (133.55, 75.4)),
             ('11', (130.4, 84.0)), ('15', (133.55, 92.45)), ('21', (142.55, 92.6))):
    track('GND', F, pad[n], v, w=0.3)
    via('GND', *v)

# zones: back ground plane into the tab, ground under the module on top, +3V3 elsewhere on top
zone_like('GND', BK, BK, 'GND', rect(125.0, 69.9, TAB_X + 0.1, TAB_B + 0.1), 11, 'RM2 tab GND')
zone_like('+3V3', F, F, '+3V3', rect(125.0, 69.9, TAB_X + 0.1, TAB_B + 0.1), 10, 'RM2 tab 3V3')
zone_like('GND', BK, F, 'GND', rect(131.3, 76.3, 143.3, 91.7), 20, 'RM2 GND under module', solid=True)

# antenna strip: no copper on any layer from the module's antenna end to the board edge
ka = pcbnew.ZONE(B)
ka.SetIsRuleArea(True)
ka.SetLayerSet(pcbnew.LSET.AllCuMask())
ka.SetDoNotAllowTracks(True)
ka.SetDoNotAllowVias(True)
ka.SetDoNotAllowPads(True)
ka.SetDoNotAllowZoneFills(True)
ka.SetDoNotAllowFootprints(False)
ka.SetZoneName('RM2 antenna strip: no copper')
ka.Outline().NewOutline()
for x, y in rect(CX + 3.3, 69.5, TAB_X + 0.5, TAB_B + 0.5):
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

# ---------------------------------------------------------------- R11: GPIO0 -> GPIO47
remove_tracks('/GPIO0', BK, ((90.9, 81.0), (93.02, 81.0)), ((93.02, 81.0), (93.1, 81.08)))
via('/GPIO47_ADC7', 112.2, 87.5)     # on Pi's GPIO47 run to J3
track('/GPIO47_ADC7', BK, (112.2, 87.5), (105.815, 81.115), (93.1, 81.115))

ni = B.GetNetInfo().GetNetItem('/FLASH2_SS')
if ni is not None:
    B.Delete(ni)

pcbnew.ZONE_FILLER(B).Fill(B.Zones())
B.Save(sys.argv[1])
