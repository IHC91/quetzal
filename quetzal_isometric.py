# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# Quetzal Piping Isometric Generator (v2)
# Branch: feat/isometric-generator

import json, math, os

# ─── CONFIG ──────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = 420, 297                     # A3 horizontal mm
SCALE = 0.030                                  # mm real → mm SVG
GAP = 18                                       # espacio entre líneas de cota
MARGIN = 25                                    # margen página

# ─── PROYECCIÓN ISOMÉTRICA ───────────────────────────────────────────────────

def iso_xy(p, ox=0, oy=0):
    """(N, E, EL) → (x_svg, y_svg)  (N=arriba, E=derecha, EL=vertical)"""
    x = (p["E"] - p["N"]) * SCALE
    y = (p["E"] + p["N"]) * 0.5 * SCALE - p["EL"] * SCALE
    return (ox + x, oy - y)

def iso_dir(d):
    d = d.upper()
    return {"E": (1,0), "W": (-1,0), "N": (0,1), "S": (0,-1),
            "UP": (0,-1), "DOWN": (0,1)}.get(d, (0,0))

def perp(dx, dy, s=3):
    h = math.hypot(dx, dy)
    return (-dy/h*s, dx/h*s) if h else (0,0)

# ─── SVG HELPERS ─────────────────────────────────────────────────────────────

def tag(name, **attrs):
    a = " ".join(f'{k}="{v}"' for k,v in attrs.items() if v is not None)
    return f"<{name} {a}/>"

def text(x, y, s, **kw):
    a = " ".join(f'{k}="{v}"' for k,v in kw.items())
    return f'<text x="{x:.1f}" y="{y:.1f}" {a}>{s}</text>'

# ─── RENDER ──────────────────────────────────────────────────────────────────

def render_isometric(data, output_path=None):
    """Genera SVG isométrico profesional a partir de dict de datos."""
    comps = data["components"]
    # Centrar en página
    xs = [iso_xy(c.get("start_coord") or c.get("position_coord"), 0, 0)[0] for c in comps if c.get("start_coord") or c.get("position_coord")]
    ys = [iso_xy(c.get("start_coord") or c.get("position_coord"), 0, 0)[1] for c in comps if c.get("start_coord") or c.get("position_coord")]
    if not xs: xs, ys = [0], [0]
    cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    ox, oy = PAGE_W/2 - cx, PAGE_H/2 - cy + 20

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" viewBox="0 0 {PAGE_W} {PAGE_H}" style="background:#fff;font-family:sans-serif;">']
    # Defs
    svg.append('<defs><marker id="arr" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="4" markerHeight="4" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#1e293b"/></marker></defs>')
    # Grid
    for gx in range(20, PAGE_W-10, 20):
        svg.append(f'<line x1="{gx}" y1="20" x2="{gx}" y2="{PAGE_H-50}" stroke="#e2e8f0" stroke-width="0.3"/>')
    for gy in range(30, PAGE_H-50, 20):
        svg.append(f'<line x1="20" y1="{gy}" x2="{PAGE_W-20}" y2="{gy}" stroke="#e2e8f0" stroke-width="0.3"/>')

    # ─── 1. TITLE BLOCK ──────────────────
    svg.append(f'<rect x="10" y="10" width="{PAGE_W-20}" height="{PAGE_H-20}" fill="none" stroke="#cbd5e1" stroke-width="1"/>')
    # Cajetín superior
    svg.append(f'<rect x="{PAGE_W-230}" y="15" width="215" height="50" fill="#f8fafc" stroke="#cbd5e1" stroke-width="0.5" rx="2"/>')
    ln = data.get("line_number", "N/A")
    svg.append(text(PAGE_W-225, 28, f"LINE: {ln}", font_size="9", font_weight="bold", fill="#0f172a"))
    svg.append(text(PAGE_W-225, 39, f"Service: {data.get('service','?')} | Fluid: {data.get('fluido','?')}", font_size="7", fill="#475569"))
    svg.append(text(PAGE_W-225, 50, f"Design: {data.get('design_pressure','?')} @ {data.get('design_temperature','?')} | Class: {data.get('piping_class','?')}", font_size="7", fill="#475569"))
    svg.append(text(PAGE_W-225, 60, f"Project: {data.get('pypeline','?')}", font_size="7", fill="#475569"))

    # Cajetín inferior
    svg.append(f'<rect x="{PAGE_W-230}" y="{PAGE_H-40}" width="215" height="25" fill="#f8fafc" stroke="#cbd5e1" stroke-width="0.5" rx="2"/>')
    svg.append(text(PAGE_W-225, PAGE_H-28, "QUETZAL ISOMETRIC DRAWING v2", font_size="8", font_weight="bold", fill="#0f172a"))
    svg.append(text(PAGE_W-225, PAGE_H-18, "IHC91/quetzal · feat/isometric-generator", font_size="7", fill="#94a3b8"))

    # ─── 2. NORTH ARROW ──────────────────
    svg.append(f'<circle cx="35" cy="35" r="10" fill="none" stroke="#1e293b" stroke-width="0.8"/>')
    svg.append(f'<polygon points="35,28 38,38 35,36 32,38" fill="#dc2626"/>')
    svg.append(text(35, 22, "N", font_size="8", text_anchor="middle", font_weight="bold", fill="#dc2626"))

    # ─── 3. FLOW DIRECTION ──────────────
    fd = data.get("flow_direction", "")
    svg.append(text(50, 22, f"Flow → {fd}", font_size="7", fill="#059669"))

    # ─── 4. PIPE + FITTINGS ──────────────
    px_prev, py_prev = None, None
    for c in comps:
        tp = c["type"]
        if tp == "Pipe":
            p1 = iso_xy(c["start_coord"], ox, oy)
            p2 = iso_xy(c["end_coord"], ox, oy)
            dx, dy = p2[0]-p1[0], p2[1]-p1[1]
            ux, uy = perp(dx, dy, 3)

            # Tubería (doble línea)
            svg.append(f'<line x1="{p1[0]+ux:.1f}" y1="{p1[1]+uy:.1f}" x2="{p2[0]+ux:.1f}" y2="{p2[1]+uy:.1f}" stroke="#2563eb" stroke-width="2.5" stroke-linecap="round"/>')
            svg.append(f'<line x1="{p1[0]-ux:.1f}" y1="{p1[1]-uy:.1f}" x2="{p2[0]-ux:.1f}" y2="{p2[1]-uy:.1f}" stroke="#2563eb" stroke-width="2.5" stroke-linecap="round"/>')
            # Centro (guión)
            svg.append(f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" stroke="#dc2626" stroke-width="0.6" stroke-dasharray="4 3" opacity="0.6"/>')

            # Cut length
            mx, my = (p1[0]+p2[0])/2, (p1[1]+p2[1])/2
            cl = c.get("cut_length_mm", c["length_mm"])
            svg.append(text(mx+ux*5, my+uy*5, f'{c["tag"]} CL={cl:.0f} mm', font_size="6.5", fill="#1e293b", text_anchor="middle"))

            # Dimensión total
            dim_p = (mx + ux*10, my + uy*10 + 8)
            svg.append(text(dim_p[0], dim_p[1], f'⌀{c["od_mm"]:.0f}x{c["thk_mm"]:.1f}', font_size="6", fill="#64748b", text_anchor="middle"))

            px_prev, py_prev = p2

        elif tp == "Elbow":
            pp = iso_xy(c["position_coord"], ox, oy)
            svg.append(f'<circle cx="{pp[0]:.1f}" cy="{pp[1]:.1f}" r="4" fill="none" stroke="#64748b" stroke-width="1.5"/>')
            svg.append(f'<text x="{pp[0]+6:.1f}" y="{pp[1]+3:.1f}" font-size="6.5" fill="#64748b">{c["tag"]} {c["angle"]}° LR</text>')

        elif tp == "Flange":
            pp = iso_xy(c["position_coord"], ox, oy)
            svg.append(f'<rect x="{pp[0]-5:.1f}" y="{pp[1]-7:.1f}" width="10" height="14" rx="1" fill="none" stroke="#64748b" stroke-width="1.5"/>')
            # Cara RF
            svg.append(f'<line x1="{pp[0]-3:.1f}" y1="{pp[1]-4:.1f}" x2="{pp[0]+3:.1f}" y2="{pp[1]-4:.1f}" stroke="#64748b" stroke-width="0.8"/>')
            svg.append(text(pp[0]+8, pp[1]+3, f'{c["tag"]} {c["dn"]} {c["schedule"]} {c["facing"]}', font_size="6", fill="#64748b"))

        elif tp == "Valve":
            pp = iso_xy(c["position_coord"], ox, oy)
            # Símbolo válvula de bola
            svg.append(f'<rect x="{pp[0]-6:.1f}" y="{pp[1]-6:.1f}" width="12" height="12" rx="2" fill="none" stroke="#dc2626" stroke-width="1.5"/>')
            svg.append(f'<line x1="{pp[0]-6:.1f}" y1="{pp[1]:.1f}" x2="{pp[0]+6:.1f}" y2="{pp[1]:.1f}" stroke="#dc2626" stroke-width="1.2"/>')
            svg.append(text(pp[0]+9, pp[1]+3, f'{c["tag"]} {c["valve_type"]} {c["schedule"]}', font_size="6", fill="#dc2626"))

    # ─── 5. WELD NUMBERS ─────────────────
    for w in data.get("welds", []):
        w_tag = w["id"]
        w_type = w["type"]
        # Buscar punto medio entre componentes
        c1 = next((x for x in comps if x["tag"] == w["between"][0]), None)
        c2 = next((x for x in comps if x["tag"] == w["between"][1]), None)
        if c1 and c2:
            p1 = iso_xy(c1.get("end_coord") or c1.get("position_coord"), ox, oy)
            p2 = iso_xy(c2.get("start_coord") or c2.get("position_coord"), ox, oy)
            mx, my = (p1[0]+p2[0])/2, (p1[1]+p2[1])/2
            color = "#dc2626" if w_type == "Field" else "#059669"
            prefix = "F" if w_type == "Field" else "S"
            svg.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="5" fill="#fff" stroke="{color}" stroke-width="1.2"/>')
            svg.append(text(mx, my+1.5, f'{prefix}{w_tag}', font_size="5.5", fill=color, text_anchor="middle", dominant_baseline="middle"))

    # ─── 6. COORDENADAS (burbujas) ──────
    drawn_positions = set()
    for c in comps:
        pp = c.get("start_coord") or c.get("position_coord")
        if pp and tuple(pp.values()) not in drawn_positions:
            drawn_positions.add(tuple(pp.values()))
            p = iso_xy(pp, ox, oy)
            svg.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="6" fill="none" stroke="#059669" stroke-width="0.8"/>')
            svg.append(text(p[0], p[1]-9, f"N {pp['N']:.0f}", font_size="6", fill="#059669", text_anchor="middle"))
            svg.append(text(p[0], p[1]+9, f"E {pp['E']:.0f}", font_size="6", fill="#059669", text_anchor="middle"))
            svg.append(text(p[0], p[1]-20, f"EL. {pp['EL']:.0f}", font_size="6", fill="#059669", text_anchor="middle"))
        # También end_coord si es pipe
        pp2 = c.get("end_coord")
        if pp2 and tuple(pp2.values()) not in drawn_positions:
            drawn_positions.add(tuple(pp2.values()))
            p = iso_xy(pp2, ox, oy)
            svg.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="6" fill="none" stroke="#059669" stroke-width="0.8"/>')
            svg.append(text(p[0], p[1]-9, f"N {pp2['N']:.0f}", font_size="6", fill="#059669", text_anchor="middle"))
            svg.append(text(p[0], p[1]+9, f"E {pp2['E']:.0f}", font_size="6", fill="#059669", text_anchor="middle"))
            svg.append(text(p[0], p[1]-20, f"EL. {pp2['EL']:.0f}", font_size="6", fill="#059669", text_anchor="middle"))

    # ─── 7. BOM TABLE ────────────────────
    bx, by = 15, PAGE_H-120
    col_w = [20, 45, 35, 25, 25, 25, 20, 20, 75]
    hdrs = ["ITEM", "TIPO", "DIÁMETRO", "NPS", "SCHED", "OD", "ESP", "CANT", "MATERIAL"]
    tw = sum(col_w)

    # Fondo
    svg.append(f'<rect x="{bx}" y="{by}" width="{tw}" height="{35+len(comps)*15+25}" fill="#f8fafc" stroke="#cbd5e1" stroke-width="0.5" rx="2"/>')
    svg.append(text(bx+5, by+14, "LISTA DE MATERIALES (BOM)", font_size="9", font_weight="bold", fill="#0f172a"))
    svg.append(f'<line x1="{bx}" y1="{by+20}" x2="{bx+tw}" y2="{by+20}" stroke="#cbd5e1" stroke-width="0.5"/>')

    x = bx
    for i,h in enumerate(hdrs):
        svg.append(text(x+3, by+34, h, font_size="6.5", font_weight="bold", fill="#0f172a"))
        x += col_w[i]

    sy = by + 38
    for idx, c in enumerate(comps, 1):
        x = bx
        dn_to_nps = {"DN100": "NPS 4", "DN80": "NPS 3", "DN50": "NPS 2",
                     "DN150": "NPS 6", "DN200": "NPS 8", "DN250": "NPS 10"}
        nps = dn_to_nps.get(c.get("dn",""), c.get("nps",""))
        row = [str(idx), c["type"], c.get("dn",""), nps,
               c.get("schedule",""),
               f'{c.get("od_mm",0):.0f}',
               f'{c.get("thk_mm",0):.1f}' if c.get("thk_mm",0) else "-",
               "1",
               c.get("material","")]
        for val in row:
            svg.append(text(x+3, sy+10, val, font_size="6", fill="#334155"))
            x += col_w[row.index(val)]
        sy += 14

    # Bolts + Gaskets
    sy += 4
    svg.append(f'<line x1="{bx}" y1="{sy-2}" x2="{bx+tw}" y2="{sy-2}" stroke="#cbd5e1" stroke-width="0.3"/>')
    svg.append(text(bx+3, sy+10, "PERNOS / ESPÁRRAGOS", font_size="6.5", font_weight="bold", fill="#0f172a"))
    sy += 14
    for b in data.get("bolts", []):
        svg.append(text(bx+3, sy+10, f'  {b["qty"]} und {b["size"]}x{b["length_mm"]}mm {b["material"]} Gr.{b["grade"]}', font_size="6", fill="#334155"))
        sy += 13
    sy += 4
    svg.append(text(bx+3, sy+10, "EMPAQUES", font_size="6.5", font_weight="bold", fill="#0f172a"))
    sy += 14
    for g in data.get("gaskets", []):
        svg.append(text(bx+3, sy+10, f'  {g["qty"]} und {g["nps"]} {g["type"]} {g["material"]} {g["rating"]}', font_size="6", fill="#334155"))
        sy += 13

    svg.append("</svg>")
    content = "\n".join(svg)

    path = output_path or "/tmp/isometric_profesional.svg"
    with open(path, "w") as f:
        f.write(content)
    return path


# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Modo standalone: cargar JSON de prueba y generar SVG
    import sys
    json_path = os.path.join(os.path.dirname(__file__), "tests", "test_data.json")
    if not os.path.exists(json_path):
        print("❌ No se encontró test_data.json")
        sys.exit(1)
    with open(json_path) as f:
        data = json.load(f)

    out = render_isometric(data)
    lines = sum(1 for _ in open(out))
    print(f"✅ Isométrico profesional generado: {out}")
    print(f"   Tamaño: {os.path.getsize(out)//1024} KB | Líneas: {lines}")
    print(f"   Componentes: {len(data['components'])}")
    print(f"   Soldaduras: {len(data.get('welds',[]))}")
    print(f"   Pernos: {sum(b['qty'] for b in data.get('bolts',[]))} und")
    print(f"   Empaques: {sum(g['qty'] for g in data.get('gaskets',[]))} und")
