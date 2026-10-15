"""Rough PNG render of a single KiCad schematic sheet (for eyeballing edits).

Usage: python3 kirender.py file.kicad_sch out.png [scale_px_per_mm] [x0 y0 x1 y1 crop in mm]
"""
import math
import sys

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont

from kisch import Sheet, kid, kids, prop, flag

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


class R:
    def __init__(self, sheet, scale, crop):
        self.sh, self.s = sheet, scale
        self.x0, self.y0, x1, y1 = crop
        self.img = Image.new('RGB', (int((x1 - self.x0) * scale), int((y1 - self.y0) * scale)), 'white')
        self.d = ImageDraw.Draw(self.img)
        self.fonts = {}

    def P(self, x, y):
        return ((x - self.x0) * self.s, (y - self.y0) * self.s)

    def font(self, mm):
        px = max(6, int(mm * self.s * 1.1))
        if px not in self.fonts:
            self.fonts[px] = ImageFont.truetype(FONT, px)
        return self.fonts[px]

    def text(self, x, y, t, mm=1.27, color='black', rot=0, anchor='lm'):
        t = t.replace('~{', '').replace('}', '')
        if not t:
            return
        f = self.font(mm)
        if rot % 180 == 90:
            w, h = self.d.textbbox((0, 0), t, font=f)[2:]
            tmp = Image.new('RGBA', (w + 4, h + 4), (255, 255, 255, 0))
            ImageDraw.Draw(tmp).text((2, 2), t, font=f, fill=color)
            tmp = tmp.rotate(90, expand=True)
            px, py = self.P(x, y)
            self.img.paste(tmp, (int(px - tmp.width / 2), int(py - tmp.height / 2)), tmp)
        else:
            self.d.text(self.P(x, y), t, font=f, fill=color, anchor=anchor)

    def line(self, pts, color='black', w=1):
        self.d.line([self.P(*p) for p in pts], fill=color, width=w)

    def symbol(self, sym):
        lib = self.sh.libs[self.sh.lib_key(sym)]
        at = kid(sym, 'at')
        X, Y, rot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0
        mir = kid(sym, 'mirror')
        mir = mir[1] if mir else None
        unit = int(kid(sym, 'unit')[1]) if kid(sym, 'unit') else 1
        a = math.radians(rot)
        c, s = round(math.cos(a)), round(math.sin(a))

        def T(px, py):
            x, y = px, -py
            x, y = x * c + y * s, -x * s + y * c
            if mir == 'x':
                y = -y
            elif mir == 'y':
                x = -x
            return X + x, Y + y

        dnp = flag(sym, 'dnp')
        col = (150, 0, 0)
        for sub in kids(lib, 'symbol'):
            u = int(sub[1].rsplit('_', 2)[1])
            if u not in (0, unit):
                continue
            for g in sub[2:]:
                if not isinstance(g, list):
                    continue
                if g[0] == 'rectangle':
                    (x1, y1), (x2, y2) = [tuple(map(float, kid(g, k)[1:3])) for k in ('start', 'end')]
                    self.line([T(x1, y1), T(x2, y1), T(x2, y2), T(x1, y2), T(x1, y1)], col)
                elif g[0] == 'polyline':
                    self.line([T(float(p[1]), float(p[2])) for p in kid(g, 'pts')[1:]], col)
                elif g[0] == 'circle':
                    cx, cy = T(*map(float, kid(g, 'center')[1:3]))
                    r = float(kid(g, 'radius')[1])
                    x0, y0 = self.P(cx - r, cy - r)
                    x1, y1 = self.P(cx + r, cy + r)
                    self.d.ellipse([x0, y0, x1, y1], outline=col)
                elif g[0] == 'arc':
                    self.line([T(*map(float, kid(g, k)[1:3])) for k in ('start', 'mid', 'end')], col)
                elif g[0] == 'pin':
                    pa = kid(g, 'at')
                    px, py, ang = float(pa[1]), float(pa[2]), float(pa[3])
                    ln = float(kid(g, 'length')[1])
                    ex = px + ln * math.cos(math.radians(ang))
                    ey = py + ln * math.sin(math.radians(ang))
                    if flag(g, 'hide') or 'hide' in g:
                        continue
                    self.line([T(px, py), T(ex, ey)], col)
                    num = kid(g, 'number')[1]
                    name = kid(g, 'name')[1]
                    mx, my = T((px + ex) / 2, (py + ey) / 2)
                    self.text(mx, my - 0.6, num, 0.9, (120, 0, 0), anchor='mb')
                    if name != '~' and ln > 0:
                        tx, ty = T(ex + 0.6 * math.cos(math.radians(ang)), ey + 0.6 * math.sin(math.radians(ang)))
                        dx = tx - T(ex, ey)[0]
                        self.text(tx, ty, name, 1.0, (0, 90, 90), anchor='lm' if dx > 0 else ('rm' if dx < 0 else 'mm'))
        for p in kids(sym, 'property'):
            if flag(p, 'hide') or p[1] not in ('Reference', 'Value'):
                continue
            pat = kid(p, 'at')
            ang = float(pat[3]) if len(pat) > 3 else 0
            self.text(float(pat[1]), float(pat[2]), p[2] + (' (DNP)' if dnp and p[1] == 'Reference' else ''),
                      1.1, (0, 0, 160) if p[1] == 'Reference' else (100, 0, 100), rot=ang + rot, anchor='mm')
        if dnp:
            x0, y0 = T(-3, 3)
            self.line([(x0, y0), (x0 + 6, y0 + 6)], 'red', 2)

    def draw(self):
        for w in kids(self.sh.root, 'wire'):
            pts = kid(w, 'pts')
            self.line([(float(p[1]), float(p[2])) for p in pts[1:]], (0, 130, 0), 2)
        for sym in self.sh.symbols:
            self.symbol(sym)
        for j in kids(self.sh.root, 'junction'):
            x, y = self.P(float(kid(j, 'at')[1]), float(kid(j, 'at')[2]))
            r = 0.5 * self.s
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=(0, 130, 0))
        for n in kids(self.sh.root, 'no_connect'):
            x, y = float(kid(n, 'at')[1]), float(kid(n, 'at')[2])
            self.line([(x - .6, y - .6), (x + .6, y + .6)], 'blue', 2)
            self.line([(x - .6, y + .6), (x + .6, y - .6)], 'blue', 2)
        for kind in ('label', 'global_label', 'hierarchical_label'):
            for lab in kids(self.sh.root, kind):
                at = kid(lab, 'at')
                ang = float(at[3]) if len(at) > 3 else 0
                anchor = {0: 'lb', 180: 'rb', 90: 'lb', 270: 'lb'}.get(int(ang), 'lb')
                self.text(float(at[1]), float(at[2]) - 0.3, lab[1], 1.1, (0, 0, 0), rot=ang, anchor=anchor)
        for t in kids(self.sh.root, 'text'):
            at = kid(t, 'at')
            for i, ln in enumerate(t[1].split('\n')):
                self.text(float(at[1]), float(at[2]) + i * 1.8, ln, 1.2, (0, 0, 180))


def main():
    sh = Sheet(sys.argv[1])
    scale = float(sys.argv[3]) if len(sys.argv) > 3 else 5
    crop = list(map(float, sys.argv[4:8])) if len(sys.argv) > 7 else [0, 0, 420, 297]
    r = R(sh, scale, crop)
    r.draw()
    r.img.save(sys.argv[2])


if __name__ == '__main__':
    main()
