"""Headless equivalent of pcbnew's Tools > Update PCB from Schematic.

Run inside KiCad's Python (e.g. the kicad/kicad:10.0 Docker image):

    kicad-cli sch export netlist --format kicadxml -o net.xml RP2350B-RM2.kicad_sch
    python3 tools/update_pcb_from_sch.py net.xml RP2350B-RM2.kicad_pcb

Matches footprints by reference. Adds missing footprints, swaps footprints whose
library ID changed (keeping position, rotation and side), deletes footprints whose
symbol is gone, copies values, fields and DNP / exclude-from-BOM flags from the
symbols, and reassigns every pad's net. New footprints are parked to the right of
the board for placement.
"""
import os
import sys
import xml.etree.ElementTree as ET

import pcbnew

PRJ = os.path.dirname(os.path.abspath(sys.argv[2]))
LIBS = {'rp2350b_rm2': os.path.join(PRJ, 'rp2350b_rm2.pretty')}
STD = '/usr/share/kicad/footprints'
SKIP_FIELDS = {'Footprint', 'Reference', 'Value'}


def lib_path(nick):
    return LIBS.get(nick, os.path.join(STD, nick + '.pretty'))


def load_fp(fpid):
    nick, name = fpid.split(':', 1)
    fp = pcbnew.FootprintLoad(lib_path(nick), name)
    if fp is None:
        raise SystemExit(f'cannot load footprint {fpid}')
    fp.SetFPIDAsString(fpid)
    return fp


def main():
    root = ET.parse(sys.argv[1]).getroot()
    board = pcbnew.LoadBoard(sys.argv[2])
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    park = [pcbnew.FromMM(135), pcbnew.FromMM(110)]

    for comp in root.find('components'):
        ref = comp.get('ref')
        props = {p.get('name'): p.get('value') for p in comp.findall('property')}
        if 'exclude_from_board' in props:
            continue
        fpid = comp.findtext('footprint')
        path = pcbnew.KIID_PATH(comp.find('sheetpath').get('tstamps').rstrip('/') + '/'
                                + comp.find('tstamps').text)
        old = fps.get(ref)
        if old is not None and old.GetFPIDAsString() == fpid:
            fp = old
        else:
            fp = load_fp(fpid)
            fp.SetReference(ref)
            board.Add(fp)  # Flip() needs the board
            if old is not None:
                if old.IsFlipped():
                    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
                fp.SetPosition(old.GetPosition())
                fp.SetOrientation(old.GetOrientation())
                for o, n in ((old.Reference(), fp.Reference()), (old.Value(), fp.Value())):
                    n.SetVisible(o.IsVisible())
                board.Remove(old)
                print(f'{ref}: {old.GetFPIDAsString()} -> {fpid}')
            else:
                fp.SetPosition(pcbnew.VECTOR2I(*park))
                park[1] += pcbnew.FromMM(6)
                print(f'{ref}: added {fpid}')
            fps[ref] = fp
        fp.SetPath(path)
        fp.SetValue(comp.findtext('value'))

        fields = comp.find('fields')
        for f in (fields if fields is not None else []):
            name, val = f.get('name'), f.text or ''
            if name in SKIP_FIELDS:
                continue
            fld = fp.GetField(name)
            if fld is None:
                fld = pcbnew.PCB_FIELD(fp, fp.GetNextFieldOrdinal(), name)
                fld.SetVisible(False)
                fld.SetLayer(pcbnew.F_Fab if not fp.IsFlipped() else pcbnew.B_Fab)
                fld.SetPosition(fp.GetPosition())
                fp.Add(fld)
            if fld.GetText() != val:
                fld.SetText(val)
        fp.SetDNP('dnp' in props)
        fp.SetExcludedFromBOM('exclude_from_bom' in props)

    # footprints whose symbol has gone from the schematic (their tracks are left for the layout pass)
    in_sch = {c.get('ref') for c in root.find('components')}
    for ref, fp in list(fps.items()):
        if ref not in in_sch and fp.GetPath().AsString():
            print(f'{ref}: removed (no symbol)')
            board.Delete(fp)
            del fps[ref]

    nets = board.GetNetInfo()
    for net in root.find('nets'):
        name = net.get('name')
        ni = nets.GetNetItem(name)
        if ni is None:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
        for node in net:
            fp = fps.get(node.get('ref'))
            if fp is None:
                continue
            for pad in fp.Pads():
                if pad.GetNumber() == node.get('pin') and pad.GetNetname() != name:
                    print(f'  {node.get("ref")}.{pad.GetNumber()}: {pad.GetNetname() or "-"} -> {name}')
                    pad.SetNet(ni)

    board.RemoveUnusedNets(None) if hasattr(board, 'RemoveUnusedNets') else None
    board.Save(sys.argv[2])


if __name__ == '__main__':
    main()
