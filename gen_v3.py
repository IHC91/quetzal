#!/usr/bin/env python3
"""Generates v3 isometric SVG with ballooning, weld numbers, proper layout."""
import json, math, os

with open('/tmp/pipe_real_v2.json') as f:
    data = json.load(f)

comps = data["components"]
welds = data.get("welds", [])

PAGE_W, PAGE_H = 420, 297
SC = 0.030

def iso(p, ox, oy):
    x = (p["E"] - p["N"]) * SC
    y = (p["E"] + p["N"]) * 0.5 * SC - p["EL"] * SC
    return (ox + x, oy - y)

def perp(dx, dy, s=3):
    h = math.hypot(dx, dy)
    return (-dy/h*s, dx/h*s) if h else (0,0)

def txt(x, y, s, **kw):
    a = " ".join(f'{k}="{v}"' for k,v in kw.items())
    return f'<text x="{x:.1f}" y="{y:.1f}" {a}>{s}</text>'

# Center
pts = []
for c in comps:
    for k in ('start_coord','end_coord','position_coord'):
        p = c.get(k)
        if p: pts.append((p["E"],p["N"],p["EL"]))
if not pts: pts = [(0,0,0)]
cx = (min(p[0] for p in pts)+max(p[0] for p in pts))/2
cz = (min(p[2] for p in pts)+max(p[2] for p in pts))/2
ox, oy = 210 - cx*SC, 160 + cz*SC

svg = []
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" viewBox="0 0 {PAGE_W} {PAGE_H}" style="background:#fff;font-family:Arial,sans-serif;">')
svg.append('<defs><marker id="arr" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="4" markerHeight="4" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#1e293b"/></marker></defs>')

# Grid
for gx in range(20, PAGE_W-10, 20):
    svg.append(f'<line x1="{gx}" y1="20" x2="{gx}" y2="{PAGE_H-60}" stroke="#e2e8f0" stroke-width="0.3"/>')
for gy in range(30, PAGE_H-60, 20):
    svg.append(f'<line x1="20" y1="{gy}" x2="{PAGE_W-20}" y2="{gy}" stroke="#e2e8f0" stroke-width="0.3"/>')

svg.append(f'<rect x="10" y="10" width="{PAGE_W-20}" height="{PAGE_H-20}" fill="none" stroke="#94a3b8" stroke-width="1.5"/>')

# Title Block
svg.append(f'<rect x="15" y="15" width="{PAGE_W-70}" height="50" fill="#f8fafc" stroke="#cbd5e1" stroke-width="0.5" rx="3"/>')
ln = data.get("line_number","N/A")
svg.append(txt(22, 28, "LINE: "+ln, font_size="11", font_weight="bold", fill="#0f172a"))
svg.append(txt(22, 41, "Service: "+data.get("service","?")+" | Fluid: "+data.get("fluido","?")+" | Design: "+data.get("design_pressure","?"), font_size="7.5", fill="#475569"))
svg.append(txt(22, 53, "Class: "+data.get("piping_class","?")+" | Project: "+data.get("pypeline","?"), font_size="7.5", fill="#475569"))

# Bottom right box
svg.append(f'<rect x="{PAGE_W-200}" y="{PAGE_H-38}" width="185" height="24" fill="#f8fafc" stroke="#cbd5e1" stroke-width="0.5" rx="2"/>')
svg.append(txt(PAGE_W-195, PAGE_H-24, "QUETZAL ISOMETRIC v3", font_size="8", font_weight="bold", fill="#0f172a"))
svg.append(txt(PAGE_W-195, PAGE_H-16, "IHC91/quetzal", font_size="6.5", fill="#94a3b8"))

# North
svg.append(f'<circle cx="30" cy="25" r="8" fill="none" stroke="#1e293b" stroke-width="0.8"/>')
svg.append(f'<polygon points="30,19 33,28 30,26 27,28" fill="#dc2626"/>')
svg.append(txt(30, 13, "N", font_size="8", text_anchor="middle", font_weight="bold", fill="#dc2626"))

# DRAW PIPING
balloon_num = 1
for c in comps:
    t = c['type']
    
    if t == 'Pipe':
        p1 = iso(c['start_coord'], ox, oy)
        p2 = iso(c['end_coord'], ox, oy)
        dx, dy = p2[0]-p1[0], p2[1]-p1[1]
        ux, uy = perp(dx, dy, 3)
        for side in [-1, 1]:
            svg.append(f'<line x1="{p1[0]+ux*side:.1f}" y1="{p1[1]+uy*side:.1f}" x2="{p2[0]+ux*side:.1f}" y2="{p2[1]+uy*side:.1f}" stroke="#2563eb" stroke-width="2" stroke-linecap="round"/>')
        svg.append(f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" stroke="#dc2626" stroke-width="0.5" stroke-dasharray="4 3" opacity="0.5"/>')
        mx, my = (p1[0]+p2[0])/2, (p1[1]+p2[1])/2
        cl = c.get('cut_length_mm', c['length_mm'])
        svg.append(txt(mx+ux*6, my+uy*6+8, "CL="+str(int(cl)), font_size="6.5", fill="#1e293b", text_anchor="middle"))
    
    elif t == 'Flange':
        pp = iso(c['position_coord'], ox, oy)
        svg.append(f'<rect x="{pp[0]-4:.1f}" y="{pp[1]-6:.1f}" width="8" height="12" rx="1" fill="none" stroke="#64748b" stroke-width="1.2"/>')
        svg.append(f'<line x1="{pp[0]-2:.1f}" y1="{pp[1]-3:.1f}" x2="{pp[0]+2:.1f}" y2="{pp[1]-3:.1f}" stroke="#64748b" stroke-width="0.6"/>')
    
    elif t == 'Tee':
        pp = iso(c['position_coord'], ox, oy)
        svg.append(f'<circle cx="{pp[0]:.1f}" cy="{pp[1]:.1f}" r="4" fill="none" stroke="#64748b" stroke-width="1.5"/>')
        svg.append(f'<line x1="{pp[0]:.1f}" y1="{pp[1]-8:.1f}" x2="{pp[0]:.1f}" y2="{pp[1]+8:.1f}" stroke="#64748b" stroke-width="1.5"/>')
    
    elif t in ('Elbow', 'Reduct'):
        pp = iso(c['position_coord'], ox, oy)
        svg.append(f'<circle cx="{pp[0]:.1f}" cy="{pp[1]:.1f}" r="4" fill="none" stroke="#64748b" stroke-width="1.5"/>')
    
    # Balloon
    if 'item_no' in c:
        pp = iso(c.get('start_coord') or c.get('position_coord') or {'N':0,'E':0,'EL':0}, ox, oy)
        angle = (balloon_num * 25) % 360
        bx = pp[0] + 11 * math.cos(math.radians(angle))
        by = pp[1] - 11 * math.sin(math.radians(angle))
        svg.append(f'<circle cx="{pp[0]:.1f}" cy="{pp[1]:.1f}" r="1.5" fill="#0f172a"/>')
        svg.append(f'<line x1="{pp[0]:.1f}" y1="{pp[1]:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="#64748b" stroke-width="0.5"/>')
        svg.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="5" fill="#fff" stroke="#1e293b" stroke-width="0.8"/>')
        svg.append(txt(bx, by+1.5, str(c['item_no']), font_size="6.5", font_weight="bold", fill="#0f172a", text_anchor="middle", dominant_baseline="middle"))
        balloon_num += 1

# Welds
for w in welds:
    c1 = next((x for x in comps if x['tag'] == w['between'][0]), None)
    c2 = next((x for x in comps if x['tag'] == w['between'][1]), None)
    if not c1 or not c2: continue
    p1 = iso(c1.get('end_coord') or c1.get('position_coord') or {'N':0,'E':0,'EL':0}, ox, oy)
    p2 = iso(c2.get('start_coord') or c2.get('position_coord') or {'N':0,'E':0,'EL':0}, ox, oy)
    mx, my = (p1[0]+p2[0])/2, (p1[1]+p2[1])/2
    color = "#dc2626" if w['type'] == 'Field' else "#059669"
    prefix = "F" if w['type'] == 'Field' else "S"
    svg.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="4" fill="#fff" stroke="{color}" stroke-width="1"/>')
    svg.append(txt(mx, my+1, prefix+w["id"], font_size="5", fill=color, text_anchor="middle", dominant_baseline="middle"))

# Coordinates
drawn = set()
for c in comps:
    for key in ['start_coord','end_coord','position_coord']:
        pp = c.get(key)
        if not pp: continue
        ks = (int(pp['N']), int(pp['E']), int(pp['EL']))
        if ks in drawn: continue
        drawn.add(ks)
        p = iso(pp, ox, oy)
        svg.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="4.5" fill="none" stroke="#059669" stroke-width="0.8"/>')
        svg.append(txt(p[0]+7, p[1]+6, f"EL {pp['EL']:.0f}", font_size="5.5", fill="#059669"))
        svg.append(txt(p[0]+7, p[1]-3, f"N{pp['N']:.0f} E{pp['E']:.0f}", font_size="5", fill="#059669"))

# BOM TABLE
bx, by = 15, PAGE_H-150
col_w = [18, 40, 32, 28, 28, 26, 22, 18, 88]
hdrs = ["#", "TIPO", "DIAMETRO", "NPS", "SCHED", "OD", "ESP", "CANT", "MATERIAL"]
tw = sum(col_w) + 5

svg.append(txt(bx+5, by-6, "LISTA DE MATERIALES (BOM)", font_size="8.5", font_weight="bold", fill="#0f172a"))
svg.append(f'<rect x="{bx}" y="{by}" width="{tw}" height="{26+len(comps)*14+35}" fill="#f8fafc" stroke="#cbd5e1" stroke-width="0.5" rx="2"/>')

x = bx+3
for i,h in enumerate(hdrs):
    svg.append(txt(x, by+11, h, font_size="6", font_weight="bold", fill="#0f172a"))
    x += col_w[i]

svg.append(f'<line x1="{bx}" y1="{by+15}" x2="{bx+tw}" y2="{by+15}" stroke="#cbd5e1" stroke-width="0.5"/>')

sy = by + 21
dn_nps = {"DN200": "NPS 8", "DN150": "NPS 6", "DN100": "NPS 4"}
for c in comps:
    x = bx + 3
    nps = dn_nps.get(c.get('dn',''), '')
    items = [str(c.get('item_no',0)), c['type'], c.get('dn',''), nps,
             c.get('schedule',''), f'{c.get("od_mm",0):.0f}',
             f'{c.get("thk_mm",0):.1f}' if c.get('thk_mm',0) else '-',
             '1', c.get('material','')]
    for i,v in enumerate(items):
        svg.append(txt(x, sy+9, v, font_size="5.5", fill="#334155"))
        x += col_w[i]
    sy += 13.5

# Fasteners summary
sy += 5
svg.append(f'<line x1="{bx}" y1="{sy-2}" x2="{bx+tw}" y2="{sy-2}" stroke="#cbd5e1" stroke-width="0.3"/>')
svg.append(txt(bx+5, sy+8, "PERNOS Y EMPAQUES:", font_size="6", font_weight="bold", fill="#0f172a"))
sy += 12
for b in data.get("bolts", []):
    len_mm = b.get('length_mm') or b.get('length', 0)
    svg.append(txt(bx+8, sy+8, f'{b["qty"]} und {b["size"]}x{len_mm}mm {b["material"]} Gr.{b["grade"]}', font_size="5.5", fill="#334155"))
    sy += 11
for g in data.get("gaskets", []):
    svg.append(txt(bx+8, sy+8, f'{g["qty"]} und {g["nps"]} {g["type"]} {g["material"]} {g["rating"]}', font_size="5.5", fill="#334155"))
    sy += 11

svg.append("</svg>")

path = "/tmp/isometric_v3.svg"
with open(path, 'w') as f:
    f.write("\n".join(svg))

print(f"✅ SVG v3 generado: {path}")
print(f"   {len(comps)} componentes, {len(welds)} soldaduras, {balloon_num-1} balloons")
