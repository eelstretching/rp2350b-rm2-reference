"""Minimal KiCad schematic reader: S-expression parser + single-sheet netlister.

Usage: python3 kisch.py file.kicad_sch [REF ...]
Prints every net (or only nets touching the given refs) and dangling pins.
"""
import math
import re
import sys
from collections import defaultdict

TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse(text):
    stack = [[]]
    for m in TOKEN.finditer(text):
        t = m.group(0)
        if t == '(':
            stack.append([])
        elif t == ')':
            node = stack.pop()
            stack[-1].append(node)
        elif t.startswith('"'):
            stack[-1].append(Str(bytes(t[1:-1], 'utf-8').decode('unicode_escape') if '\\' in t else t[1:-1]))
        else:
            stack[-1].append(t)
    return stack[0][0]


class Str(str):
    """Quoted string atom (to tell "x" from x)."""


def kids(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def kid(node, name):
    k = kids(node, name)
    return k[0] if k else None


def prop(node, name):
    for p in kids(node, 'property'):
        if p[1] == name:
            return p[2]
    return None


def flag(node, name):
    k = kid(node, name)
    return k is not None and len(k) > 1 and k[1] == 'yes'


def key(x, y):
    return (round(float(x) * 100), round(float(y) * 100))


class Sheet:
    def __init__(self, path):
        self.root = parse(open(path, encoding='utf-8').read())
        self.libs = {}
        for sym in kids(kid(self.root, 'lib_symbols'), 'symbol'):
            self.libs[sym[1]] = sym
        self.symbols = kids(self.root, 'symbol')

    def lib_pins(self, lib_id, unit, body_style=1):
        lib = self.libs[lib_id]
        out = []
        for sub in kids(lib, 'symbol'):
            m = re.match(r'.*_(\d+)_(\d+)$', sub[1])
            u, s = int(m.group(1)), int(m.group(2))
            if u not in (0, unit) or s not in (0, body_style):
                continue
            for p in kids(sub, 'pin'):
                at = kid(p, 'at')
                out.append(dict(num=kid(p, 'number')[1], name=kid(p, 'name')[1],
                                x=float(at[1]), y=float(at[2]), etype=p[1],
                                hidden=flag(p, 'hide') or 'hide' in p))
        return out

    def is_power(self, lib_id):
        return kid(self.libs[lib_id], 'power') is not None

    def lib_key(self, sym):
        ln = kid(sym, 'lib_name')
        return ln[1] if ln else kid(sym, 'lib_id')[1]

    def placed_pins(self, sym):
        lib_id = self.lib_key(sym)
        at = kid(sym, 'at')
        X, Y, rot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
        mir = kid(sym, 'mirror')
        mir = mir[1] if mir else None
        unit = int(kid(sym, 'unit')[1]) if kid(sym, 'unit') else 1
        bs = kid(sym, 'body_style') or kid(sym, 'convert')
        bs = int(bs[1]) if bs else 1
        res = []
        for p in self.lib_pins(lib_id, unit, bs):
            x, y = p['x'], -p['y']          # lib is Y-up, sheet is Y-down
            # KiCad applies rotation, then mirror (in sheet coordinates)
            a = math.radians(rot)
            c, s = round(math.cos(a)), round(math.sin(a))
            x, y = x * c + y * s, -x * s + y * c
            if mir == 'x':
                y = -y
            elif mir == 'y':
                x = -x
            res.append(dict(p, ax=X + x, ay=Y + y))
        return res

    def netlist(self):
        parent = {}

        def find(a):
            parent.setdefault(a, a)
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        wires = []
        for w in kids(self.root, 'wire'):
            pts = kid(w, 'pts')
            (_, x1, y1), (_, x2, y2) = pts[1], pts[2]
            a, b = key(x1, y1), key(x2, y2)
            union(('pt', a), ('pt', b))
            wires.append((a, b))

        points = set()  # every connection point that may sit on a wire interior
        names = defaultdict(set)
        pins = []
        for sym in self.symbols:
            lib_id = self.lib_key(sym)
            ref = prop(sym, 'Reference')
            power = self.is_power(lib_id)
            for p in self.placed_pins(sym):
                k = key(p['ax'], p['ay'])
                points.add(k)
                node = ('pin', ref, p['num'])
                union(node, ('pt', k))
                if power and p['etype'] == 'power_in':
                    union(node, ('net', prop(sym, 'Value')))
                elif power:
                    pass  # PWR_FLAG and friends: a connection point, not a net name
                else:
                    pins.append((ref, p['num'], p['name'], k, p['etype']))
        for kind in ('label', 'global_label', 'hierarchical_label'):
            for lab in kids(self.root, kind):
                at = kid(lab, 'at')
                k = key(at[1], at[2])
                points.add(k)
                union(('pt', k), ('net', lab[1]))
        for j in kids(self.root, 'junction'):
            at = kid(j, 'at')
            points.add(key(at[1], at[2]))
        nc = set()
        for n in kids(self.root, 'no_connect'):
            at = kid(n, 'at')
            nc.add(key(at[1], at[2]))
        for (x, y) in [p for w in wires for p in w]:
            points.add((x, y))
        # anything lying on a wire (ends or interior) joins that wire
        for a, b in wires:
            for k in points:
                if on_segment(k, a, b):
                    union(('pt', k), ('pt', a))

        groups = defaultdict(list)
        netnames = defaultdict(set)
        for node in list(parent):
            r = find(node)
            if node[0] == 'pin':
                groups[r].append(node)
            elif node[0] == 'net':
                netnames[r].add(node[1])
        pinfo = {(r, n): (nm, k, et) for r, n, nm, k, et in pins}
        nets = []
        for r, members in groups.items():
            members = [m for m in members if (m[1], m[2]) in pinfo]
            nm = sorted(netnames.get(r, []))
            nets.append(dict(names=nm, pins=sorted((m[1], m[2], pinfo[(m[1], m[2])][0]) for m in members)))
        # dangling = pins alone on their net with no no_connect flag and no name
        dangling = [n['pins'][0] for n in nets
                    if len(n['pins']) == 1 and not n['names']
                    and pinfo[(n['pins'][0][0], n['pins'][0][1])][1] not in nc]
        return nets, dangling


def on_segment(k, a, b):
    (x, y), (x1, y1), (x2, y2) = k, a, b
    if (x - x1) * (y2 - y1) != (y - y1) * (x2 - x1):
        return False
    return min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)


def main():
    sh = Sheet(sys.argv[1])
    refs = set(sys.argv[2:])
    nets, dangling = sh.netlist()
    for n in sorted(nets, key=lambda n: (n['names'] or ['~'], n['pins'])):
        if refs and not any(p[0] in refs for p in n['pins']):
            continue
        label = '/'.join(n['names']) or '(unnamed)'
        print(f"{label}: " + ' '.join(f"{r}.{num}({nm})" for r, num, nm in n['pins']))
    print('DANGLING:', ' '.join(f"{r}.{num}({nm})" for r, num, nm in dangling) or 'none')
    multi = [n for n in nets if len(n['names']) > 1]
    print('MULTI-NAMED NETS:', '; '.join('/'.join(n['names']) for n in multi) or 'none')


if __name__ == '__main__':
    main()
