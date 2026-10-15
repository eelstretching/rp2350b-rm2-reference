"""Write the RM2 footprint (KiCad 10 format). Geometry from the RM2 datasheet:
21 castellated pads at 1.5 mm pitch on three sides of a 14.5 x 16.5 mm module,
antenna at the end above pins 1 and 21. Pads run 0.5 mm past the module edge
to make hand soldering easier.

python3 rm2_footprint.py out.kicad_mod
"""
import sys
import uuid


def U():
    return str(uuid.uuid4())


W, H = 7.25, 8.25            # module half-width / half-height
ANT_Y = -3.3                 # antenna keep-out runs from the top edge down to here
CU = ('"F.Cu" "B.Cu" "In1.Cu" "In2.Cu" "In3.Cu" "In4.Cu" "In5.Cu" "In6.Cu" "In7.Cu" "In8.Cu" "In9.Cu" '
      '"In10.Cu" "In11.Cu" "In12.Cu" "In13.Cu" "In14.Cu" "In15.Cu" "In16.Cu" "In17.Cu" "In18.Cu" "In19.Cu" '
      '"In20.Cu" "In21.Cu" "In22.Cu" "In23.Cu" "In24.Cu" "In25.Cu" "In26.Cu" "In27.Cu" "In28.Cu" "In29.Cu" '
      '"In30.Cu"')


def font(size=1, thick=0.15):
    return f'(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size})\n\t\t\t\t(thickness {thick})\n\t\t\t)\n\t\t)'


def prop(name, val, x, y, layer, hide=False):
    h = '\n\t\t(hide yes)' if hide else ''
    unl = '\n\t\t(unlocked yes)' if hide else ''
    return (f'\t(property "{name}" "{val}"\n\t\t(at {x:g} {y:g} 0){unl}\n\t\t(layer "{layer}"){h}\n'
            f'\t\t(uuid "{U()}")\n\t\t{font()}\n\t)\n')


def line(x1, y1, x2, y2, layer, w):
    return (f'\t(fp_line\n\t\t(start {x1:g} {y1:g})\n\t\t(end {x2:g} {y2:g})\n\t\t(stroke\n\t\t\t(width {w})\n'
            f'\t\t\t(type solid)\n\t\t)\n\t\t(layer "{layer}")\n\t\t(uuid "{U()}")\n\t)\n')


def rect(x1, y1, x2, y2, layer, w):
    return ''.join(line(*seg, layer, w) for seg in
                   ((x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1)))


def txt(t, x, y, layer, size=1):
    return (f'\t(fp_text user "{t}"\n\t\t(at {x:g} {y:g} 0)\n\t\t(layer "{layer}")\n\t\t(uuid "{U()}")\n'
            f'\t\t{font(size, 0.15 if size >= 1 else 0.1)}\n\t)\n')


def pad(n, x, y, w, h):
    return (f'\t(pad "{n}" smd rect\n\t\t(at {x:g} {y:g})\n\t\t(size {w:g} {h:g})\n'
            f'\t\t(layers "F.Cu" "F.Mask" "F.Paste")\n\t\t(uuid "{U()}")\n\t)\n')


def main():
    out = ['(footprint "RPi_RM2"\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
           '\t(layer "F.Cu")\n'
           '\t(descr "Raspberry Pi Radio Module 2 (RM2, CYW43439), 21 castellated pads, 1.5 mm pitch, '
           '14.5 x 16.5 mm; pads extended 0.5 mm for hand soldering")\n'
           '\t(tags "RM2 CYW43439 wifi bluetooth raspberry pi radio module")\n']
    out.append(prop('Reference', 'REF**', 0, -9.6, 'F.SilkS'))
    out.append(prop('Value', 'RPi_RM2', 0, 10.2, 'F.Fab'))
    out.append(prop('Datasheet', 'https://datasheets.raspberrypi.com/rm2/rm2-datasheet.pdf', 0, 0, 'F.Fab', True))
    out.append(prop('Description', 'Raspberry Pi Radio Module 2', 0, 0, 'F.Fab', True))
    out.append('\t(attr smd)\n\t(duplicate_pad_numbers_are_jumpers no)\n')

    # silkscreen: top edge and the upper part of both sides (clear of the pads), pin-1 arrow
    s = 0.12
    out.append(line(-W - s, -H - s, W + s, -H - s, 'F.SilkS', 0.12))
    out.append(line(-W - s, -H - s, -W - s, -3.4, 'F.SilkS', 0.12))
    out.append(line(W + s, -H - s, W + s, -3.4, 'F.SilkS', 0.12))
    out.append(f'\t(fp_poly\n\t\t(pts\n\t\t\t(xy -8.1 -2.55) (xy -8.6 -2.85) (xy -8.6 -2.25) (xy -8.1 -2.55)\n\t\t)\n'
               f'\t\t(stroke\n\t\t\t(width 0.12)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill yes)\n'
               f'\t\t(layer "F.SilkS")\n\t\t(uuid "{U()}")\n\t)\n')
    # fab: module body, antenna area, pin-1 chamfer
    out.append(line(-W + 1, -H, W, -H, 'F.Fab', 0.1))
    out.append(line(W, -H, W, H, 'F.Fab', 0.1))
    out.append(line(W, H, -W, H, 'F.Fab', 0.1))
    out.append(line(-W, H, -W, -H + 1, 'F.Fab', 0.1))
    out.append(line(-W, -H + 1, -W + 1, -H, 'F.Fab', 0.1))
    out.append(line(-W, ANT_Y, W, ANT_Y, 'F.Fab', 0.1))
    out.append(txt('${REFERENCE}', 0, 2.5, 'F.Fab'))
    # antenna keep-out marking
    out.append(rect(-W, -H, W, ANT_Y, 'Cmts.User', 0.1))
    out.append(txt('Antenna: no copper below', 0, -5.8, 'Cmts.User', 0.8))
    out.append(txt('Antenna end at board edge', 0, -11, 'Cmts.User', 0.8))
    # courtyard
    out.append(rect(-8.0, -8.5, 8.0, 9.0, 'F.CrtYd', 0.05))

    for n in range(1, 8):
        out.append(pad(n, -6.75, -2.55 + 1.5 * (n - 1), 2, 1))
    for n in range(8, 15):
        out.append(pad(n, -4.5 + 1.5 * (n - 8), 7.75, 1, 2))
    for n in range(15, 22):
        out.append(pad(n, 6.75, 6.45 - 1.5 * (n - 15), 2, 1))

    out.append(f'\t(zone\n\t\t(layers {CU})\n\t\t(uuid "{U()}")\n\t\t(name "RM2 antenna keep-out")\n'
               '\t\t(hatch full 0.508)\n\t\t(connect_pads\n\t\t\t(clearance 0)\n\t\t)\n\t\t(min_thickness 0.254)\n'
               '\t\t(keepout\n\t\t\t(tracks not_allowed)\n\t\t\t(vias not_allowed)\n\t\t\t(pads not_allowed)\n'
               '\t\t\t(copperpour not_allowed)\n\t\t\t(footprints allowed)\n\t\t)\n'
               '\t\t(placement\n\t\t\t(enabled no)\n\t\t\t(sheetname "")\n\t\t)\n'
               '\t\t(fill\n\t\t\t(thermal_gap 0.508)\n\t\t\t(thermal_bridge_width 0.508)\n'
               '\t\t\t(island_removal_mode 0)\n\t\t)\n'
               f'\t\t(polygon\n\t\t\t(pts\n\t\t\t\t(xy {-W} {-H}) (xy {W} {-H}) (xy {W} {ANT_Y}) (xy {-W} {ANT_Y})\n'
               '\t\t\t)\n\t\t)\n\t)\n')
    out.append('\t(embedded_fonts no)\n)\n')
    open(sys.argv[1], 'w').write(''.join(out))


if __name__ == '__main__':
    main()
