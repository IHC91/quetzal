# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
#
# Quetzal Isometric Drawing Generator (ISOGEN-lite)
#
# Generates piping isometric drawings from Quetzal pipe networks.
# Two modes:
#   1. "ISOGEN" SVG mode (standalone Python) → viewable in browser
#   2. TechDraw mode (inside FreeCAD GUI)  → integrates with TechDraw
#
# Usage inside FreeCAD:
#   from quetzal_isometric import CmdGenerateIsometric
#   Gui.addCommand("Quetzal_Isometric", CmdGenerateIsometric())
#
# Usage standalone (Python virtual env):
#   python3 quetzal_isometric.py --input model.json --output isometric.svg
#
# Commands registered:
#   Quetzal_Isometric          Isometric from selection
#   Quetzal_Isometric_Full     Isometric from whole pypeline
#
# Branch: feat/isometric-generator
# Repo:   https://github.com/IHC91/quetzal

import os
import math
import json
from math import cos, sin, radians

try:
    import FreeCAD
    import FreeCADGui
    import Part
    from PySide import QtGui
    HAS_FREECAD = True
except ImportError:
    HAS_FREECAD = False
    import subprocess
    import sys

# ─── CONFIG ──────────────────────────────────────────────────────────────────

ISOMETRIC_SCALE = 0.027            # mm real → mm dibujo isométrico
PAGE_W = 420                        # A3 horizontal (mm)
PAGE_H = 297

COLOR_PIPE = "#2563eb"              # Azul tubería
COLOR_CENTERLINE = "#dc2626"        # Rojo línea de centro
COLOR_DIM = "#1e293b"               # Cotas
COLOR_ELEV = "#059669"              # Elevaciones
COLOR_BOM_BG = "#f1f5f9"            # Fondo BOM
COLOR_BORDER = "#cbd5e1"            # Bordes
COLOR_GRID = "#e2e8f0"              # Grid/cuadrícula

FONT = "ui-monospace, monospace"
FONT_SIZE = 10
DIM_FONT_SIZE = 9

# ─── PROYECCIÓN ISOMÉTRICA ──────────────────────────────────────────────────

def iso_project(point):
    """Proyección isométrica estándar (FreeCAD vector → 2D SVG)."""
    if hasattr(point, 'x'):
        x = point.x - point.y
        y = (point.x + point.y) * 0.5 - point.z
    else:
        x = point[0] - point[1]
        y = (point[0] + point[1]) * 0.5 - point[2]
    return (x * ISOMETRIC_SCALE, y * ISOMETRIC_SCALE)


def iso_direction(vec):
    """Proyecta un vector dirección a 2D isométrico (normalizado)."""
    x = vec.x - vec.y
    y = (vec.x + vec.y) * 0.5 - vec.z
    mag = math.hypot(x, y)
    if mag < 1e-8:
        return (0, 0)
    return (x / mag, y / mag)


# ─── PARSER DE OBJETOS QUETZAL ──────────────────────────────────────────────

def _get_pype_objects(use_selection=True):
    """Obtiene objetos de tubería desde FreeCAD o desde un archivo JSON."""
    doc = FreeCAD.ActiveDocument
    if not doc:
        FreeCAD.Console.PrintError("No hay documento activo\n")
        return {}

    obj_groups = {}

    if use_selection:
        sel = FreeCADGui.Selection.getSelection()
    else:
        sel = doc.Objects

    # Filtrar objetos de tubería
    for obj in sel:
        ptype = getattr(obj, "PType", "")
        if ptype not in ("Pipe", "Elbow", "Flange", "Reduct", "Tee",
                         "Cap", "Valve", "Gasket", "Ubolt"):
            continue

        # Asignar a grupo (PypeLine u objeto suelto)
        grp = "Seleccion"
        for io in getattr(obj, "InList", []):
            if getattr(io, "PType", "") == "PypeLine":
                grp = io.Label
                break

        if grp not in obj_groups:
            obj_groups[grp] = []
        obj_groups[grp].append(obj)

    return obj_groups


def _bbox(objects):
    """Calcula el bounding box de una lista de objetos."""
    bb = None
    for obj in objects:
        try:
            s = obj.Shape
            if s:
                bb = s.BoundBox if bb is None else bb.add(s.BoundBox)
        except Exception:
            continue
    return bb


def _get_pipe_centerline(obj):
    """Extrae línea de centro de un Pipe o Elbow como lista de puntos 3D."""
    pts = []
    try:
        if getattr(obj, "PType", "") == "Pipe":
            h = getattr(obj, "Height", 0) or obj.Shape.BoundBox.ZLength
            p1 = FreeCAD.Vector(0, 0, 0)
            p2 = FreeCAD.Vector(0, 0, h)
            # Transformar por placement
            pl = obj.Placement
            pts = [pl.multVec(p1), pl.multVec(p2)]

        elif getattr(obj, "PType", "") == "Elbow":
            # Codo: tomar puertos
            if hasattr(obj, "Ports") and len(obj.Ports) >= 2:
                pl = obj.Placement
                for p in obj.Ports:
                    pts.append(pl.multVec(p))
            else:
                # Fallback: puntos extremos del shape
                bb = obj.Shape.BoundBox
                pts = [bb.Center, FreeCAD.Vector(bb.Center.x, bb.Center.y, bb.Center.z)]

        else:
            # Otros fittings: centro del shape
            bb = obj.Shape.BoundBox
            pts = [bb.Center]
    except Exception:
        pass

    return pts


# ─── GENERADOR SVG ──────────────────────────────────────────────────────────

def _svg_header():
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg"
     width="{PAGE_W}mm" height="{PAGE_H}mm"
     viewBox="0 0 {PAGE_W} {PAGE_H}"
     style="background:#fff;font-family:{FONT};">
<defs>
  <marker id="arr" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="4" markerHeight="4" orient="auto">
    <path d="M0,0 L6,3 L0,6" fill="{COLOR_DIM}" opacity="0.6"/>
  </marker>
  <marker id="circle" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="5" markerHeight="5">
    <circle cx="3" cy="3" r="2.5" fill="none" stroke="{COLOR_ELEV}" stroke-width="0.5"/>
  </marker>
</defs>
'''


def _svg_footer():
    return "</svg>"


def _iso2svg(points_2d, offset_x, offset_y):
    """Convierte puntos 2D isométricos a coordenadas SVG con offset."""
    return [(offset_x + p[0], offset_y - p[1]) for p in points_2d]


def _draw_pipe_centerline(svg, p1, p2, offset_x, offset_y):
    """Dibuja una tubería como línea isométrica con centro y grosor."""
    p1_svg = (offset_x + p1[0], offset_y - p1[1])
    p2_svg = (offset_x + p2[0], offset_y - p2[1])

    # Línea de centro
    svg.append(
        f'<line x1="{p1_svg[0]:.1f}" y1="{p1_svg[1]:.1f}" '
        f'x2="{p2_svg[0]:.1f}" y2="{p2_svg[1]:.1f}" '
        f'stroke="{COLOR_CENTERLINE}" stroke-width="1" opacity="0.5"/>'
    )

    # Tubería (desplazada para efecto 3D)
    dx = p2_svg[0] - p1_svg[0]
    dy = p2_svg[1] - p1_svg[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return
    ux, uy = -dy / length * 3, dx / length * 3  # perpendicular

    svg.append(
        f'<line x1="{p1_svg[0]+ux:.1f}" y1="{p1_svg[1]+uy:.1f}" '
        f'x2="{p2_svg[0]+ux:.1f}" y2="{p2_svg[1]+uy:.1f}" '
        f'stroke="{COLOR_PIPE}" stroke-width="2.5" stroke-linecap="round"/>'
    )
    svg.append(
        f'<line x1="{p1_svg[0]-ux:.1f}" y1="{p1_svg[1]-uy:.1f}" '
        f'x2="{p2_svg[0]-ux:.1f}" y2="{p2_svg[1]-uy:.1f}" '
        f'stroke="{COLOR_PIPE}" stroke-width="2.5" stroke-linecap="round"/>'
    )

    # Dimensión de longitud
    mid_x = (p1_svg[0] + p2_svg[0]) / 2 + ux * 2.5
    mid_y = (p1_svg[1] + p2_svg[1]) / 2 + uy * 2.5
    dim_len = math.hypot(dx, dy)
    svg.append(
        f'<text x="{mid_x:.1f}" y="{mid_y:.1f}" '
        f'font-size="{DIM_FONT_SIZE}" fill="{COLOR_DIM}" '
        f'text-anchor="middle" dominant-baseline="auto">'
        f'{dim_len:.0f} mm</text>'
    )

    return (p1_svg, p2_svg)


def _draw_component_symbol(svg, pos_2d, label, offset_x, offset_y):
    """Dibuja símbolo para fitting (codo, brida, válvula)."""
    px = offset_x + pos_2d[0]
    py = offset_y - pos_2d[1]

    svg.append(
        f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" '
        f'fill="none" stroke="#64748b" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text x="{px+6:.1f}" y="{py+3:.1f}" '
        f'font-size="7" fill="#64748b" '
        f'dominant-baseline="middle">{label}</text>'
    )


def _draw_elevation(svg, pos_2d, elev, offset_x, offset_y, label=""):
    """Dibuja burbuja de elevación."""
    px = offset_x + pos_2d[0]
    py = offset_y - pos_2d[1]

    svg.append(
        f'<circle cx="{px:.1f}" cy="{py:.1f}" r="6" '
        f'fill="none" stroke="{COLOR_ELEV}" stroke-width="1"/>'
    )
    svg.append(
        f'<text x="{px:.1f}" y="{py-9:.1f}" '
        f'font-size="7" fill="{COLOR_ELEV}" text-anchor="middle">'
        f'EL. {elev:.0f}</text>'
    )
    if label:
        svg.append(
            f'<text x="{px:.1f}" y="{py+3:.1f}" '
            f'font-size="6" fill="{COLOR_ELEV}" text-anchor="middle">'
            f'{label}</text>'
        )


def _draw_bom_table(svg, bom_data):
    """Dibuja tabla de lista de materiales."""
    x0, y0 = 15, PAGE_H - 110
    col_w = [30, 55, 55, 35, 35, 35, 35, 40]
    headers = ["ITEM", "TIPO", "TAMAÑO", "SCHED", "OD", "THK", "CANT", "MATERIAL"]
    rows = []

    for i, item in enumerate(bom_data, 1):
        rows.append([
            str(i),
            item["type"],
            item["size"],
            item["rating"],
            f"{item['od']:.1f}" if item["od"] else "-",
            f"{item['thk']:.1f}" if item["thk"] else "-",
            str(item["qty"]),
            item.get("material", "Acero al Carbón"),
        ])

    total_w = sum(col_w)
    svg.append(  # Fondo tabla
        f'<rect x="{x0}" y="{y0}" width="{total_w}" height="{35+len(rows)*18}" '
        f'fill="{COLOR_BOM_BG}" stroke="{COLOR_BORDER}" stroke-width="0.5" rx="2"/>'
    )

    svg.append(  # Título
        f'<text x="{x0+5}" y="{y0+14}" font-size="9" font-weight="bold" '
        f'fill="{COLOR_DIM}">LISTA DE MATERIALES (BOM)</text>'
    )

    # Headers
    x = x0
    svg.append(f'<line x1="{x0}" y1="{y0+20}" x2="{x0+total_w}" y2="{y0+20}" '
               f'stroke="{COLOR_BORDER}" stroke-width="0.5"/>')
    for i, h in enumerate(headers):
        svg.append(
            f'<text x="{x+3}" y="{y0+34}" font-size="7" '
            f'font-weight="bold" fill="{COLOR_DIM}">{h}</text>'
        )
        x += col_w[i]

    # Rows
    sy = y0 + 38
    for row in rows:
        x = x0
        for i, val in enumerate(row):
            svg.append(
                f'<text x="{x+3}" y="{sy+10}" font-size="6.5" '
                f'fill="#334155">{val}</text>'
            )
            x += col_w[i]
        sy += 16


def _draw_border(svg, title="QUETZAL ISOMETRIC DRAWING"):
    """Dibuja marco y cajetín."""
    # Margen
    svg.append(
        f'<rect x="10" y="10" width="{PAGE_W-20}" height="{PAGE_H-20}" '
        f'fill="none" stroke="{COLOR_BORDER}" stroke-width="1"/>'
    )
    # Cajetín
    svg.append(
        f'<rect x="{PAGE_W-200}" y="{PAGE_H-40}" width="185" height="25" '
        f'fill="none" stroke="{COLOR_BORDER}" stroke-width="0.5"/>'
    )
    svg.append(
        f'<text x="{PAGE_W-195}" y="{PAGE_H-28}" font-size="8" '
        f'fill="#475569">{title}</text>'
    )
    svg.append(
        f'<text x="{PAGE_W-195}" y="{PAGE_H-18}" font-size="7" '
        f'fill="#94a3b8">Quetzal WB · IHC91/quetzal</text>'
    )
    # Grid
    for gx in range(20, PAGE_W-20, 20):
        svg.append(
            f'<line x1="{gx}" y1="20" x2="{gx}" y2="{PAGE_H-50}" '
            f'stroke="{COLOR_GRID}" stroke-width="0.3"/>'
        )
    for gy in range(30, PAGE_H-50, 20):
        svg.append(
            f'<line x1="20" y1="{gy}" x2="{PAGE_W-20}" y2="{gy}" '
            f'stroke="{COLOR_GRID}" stroke-width="0.3"/>'
        )


# ─── FUNCIÓN PRINCIPAL ──────────────────────────────────────────────────────

def generate_isometric(use_selection=True, output_path=None):
    """
    Genera un dibujo isométrico en SVG de la tubería de Quetzal.

    Parámetros:
        use_selection (bool): True = usar selección, False = todo el doc
        output_path (str):  Ruta SVG. Si None, se usa un nombre automático.

    Retorna dict con resultados o None si falla.
    """
    try:
        doc = FreeCAD.ActiveDocument
    except Exception:
        FreeCAD.Console.PrintError("FreeCAD no disponible\n")
        return None

    if not doc:
        FreeCAD.Console.PrintError("No hay documento activo\n")
        return None

    FreeCAD.Console.PrintMessage("═" * 50 + "\n")
    FreeCAD.Console.PrintMessage("🏗️  QUETZAL ISOMETRIC GENERATOR\n")
    FreeCAD.Console.PrintMessage("═" * 50 + "\n")

    # ── 1. Obtener objetos ──
    groups = _get_pype_objects(use_selection)
    if not groups:
        FreeCAD.Console.PrintError("No se encontraron objetos de tubería\n")
        FreeCAD.Console.PrintMessage(
            "💡 Selecciona tuberías o pypelines y vuelve a intentar.\n")
        return None

    # Usar el primer grupo disponible
    grp_name = list(groups.keys())[0]
    objects = groups[grp_name]

    FreeCAD.Console.PrintMessage(f"📦 Grupo: '{grp_name}' | "
                                 f"{len(objects)} componentes\n")

    # ── 2. Calcular bounding box para centrar el dibujo ──
    bb = _bbox(objects)
    if not bb:
        FreeCAD.Console.PrintError("No se pudo calcular bounding box\n")
        return None

    # Centro del modelo en 3D → centrar en página SVG
    center_3d = bb.Center
    offset_x = PAGE_W / 2
    offset_y = PAGE_H / 2 + 20

    # ── 3. Generar SVG ──
    svg_parts = [_svg_header()]
    _draw_border(svg_parts, f"ISOMÉTRICO — {grp_name}")

    # Dibujar cada componente
    total_pipes = 0
    total_fittings = 0
    elevations_drawn = 0
    bom = {}

    for obj in objects:
        ptype = getattr(obj, "PType", "?")
        psize = getattr(obj, "PSize", "")
        rating = getattr(obj, "PRating", "")
        od = getattr(obj, "OD", 0)
        thk = getattr(obj, "thk", 0)

        # Acumular BOM
        key = (ptype, psize, rating)
        if key not in bom:
            bom[key] = {
                "type": ptype, "size": psize, "rating": rating,
                "od": od, "thk": thk, "qty": 0, "material": "Acero al Carbón",
            }
        bom[key]["qty"] += 1

        # Extraer puntos de centro
        pts = _get_pipe_centerline(obj)
        if len(pts) < 1:
            continue

        pts_2d = [iso_project(p) for p in pts]

        if ptype == "Pipe":
            if len(pts_2d) >= 2:
                _draw_pipe_centerline(svg_parts, pts_2d[0], pts_2d[1],
                                      offset_x, offset_y)
                total_pipes += 1

                # Elevación en inicio y fin del pipe
                _draw_elevation(svg_parts, pts_2d[0], pts[0].z,
                                offset_x, offset_y, obj.Label)
                _draw_elevation(svg_parts, pts_2d[-1], pts[-1].z,
                                offset_x, offset_y, "")
                elevations_drawn += 2

        elif ptype == "Elbow":
            if pts_2d:
                _draw_component_symbol(svg_parts, pts_2d[0], f"Codo {psize}",
                                       offset_x, offset_y)
                total_fittings += 1
                _draw_elevation(svg_parts, pts_2d[0], pts[0].z,
                                offset_x, offset_y, obj.Label)
                elevations_drawn += 1

        else:
            # Flange, Valve, etc.
            if pts_2d:
                label_map = {"Flange": "B", "Valve": "Vlv",
                             "Reduct": "Red", "Tee": "T", "Cap": "Cp",
                             "Gasket": "Emp", "Ubolt": "U"}
                symbol = label_map.get(ptype, ptype[:3])
                _draw_component_symbol(svg_parts, pts_2d[0],
                                       f"{symbol} {psize}",
                                       offset_x, offset_y)
                total_fittings += 1

    # BOM
    bom_sorted = sorted(bom.values(),
                        key=lambda x: {"Pipe": 1, "Elbow": 2, "Tee": 3,
                                       "Reduct": 4, "Flange": 5, "Valve": 6,
                                       "Gasket": 7, "Ubolt": 8, "Cap": 9}
                        .get(x["type"], 99))
    _draw_bom_table(svg_parts, bom_sorted)

    svg_parts.append(_svg_footer())
    svg_content = "\n".join(svg_parts)

    # ── 4. Guardar SVG ──
    if not output_path:
        output_path = f"/tmp/isometric_{grp_name}_{doc.Label}.svg"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    FreeCAD.Console.PrintMessage(f"📄 SVG guardado: {output_path}\n")
    FreeCAD.Console.PrintMessage(
        f"📊 Resumen: {total_pipes} tuberías, {total_fittings} fittings, "
        f"{elevations_drawn} elevaciones, {len(bom_sorted)} items BOM\n")
    FreeCAD.Console.PrintMessage("═" * 50 + "\n")

    return {
        "path": output_path,
        "pipes": total_pipes,
        "fittings": total_fittings,
        "elevations": elevations_drawn,
        "bom_items": len(bom_sorted),
    }


# ─── COMANDOS FREECAD ───────────────────────────────────────────────────────

class CmdGenerateIsometric:
    """Genera isométrico de los objetos seleccionados."""

    def GetResources(self):
        return {
            "Pixmap": __file__.rsplit("/", 1)[0]
                      + "/iconz/quetzal_isometric.svg",
            "MenuText": "Generar Isométrico (Selección)",
            "ToolTip": "Genera dibujo isométrico SVG de la tubería "
                       "seleccionada",
            "Accel": "I",
        }

    def Activated(self):
        from PySide import QtGui
        try:
            result = generate_isometric(use_selection=True)
            if result:
                msg = (f"✅ Isométrico generado\n"
                       f"   Tuberías: {result['pipes']}\n"
                       f"   Fittings: {result['fittings']}\n"
                       f"   Elevaciones: {result['elevations']}\n"
                       f"   Items BOM: {result['bom_items']}\n"
                       f"   Archivo: {result['path']}")
                FreeCAD.Console.PrintMessage(msg + "\n")

                # Preguntar si abrir el SVG
                reply = QtGui.QMessageBox.question(
                    None, "Isométrico Generado",
                    f"{msg}\n\n¿Abrir el SVG en el navegador?",
                    QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
                if reply == QtGui.QMessageBox.Yes:
                    import subprocess
                    subprocess.Popen(["xdg-open", result["path"]])
        except Exception as e:
            FreeCAD.Console.PrintError(f"Error: {e}\n")

    def IsActive(self):
        """Activo solo si hay documento y selección de tubería."""
        doc = FreeCAD.ActiveDocument
        if not doc:
            return False
        sel = FreeCADGui.Selection.getSelection()
        pipe_objs = [o for o in sel
                     if hasattr(o, "PType")
                     and o.PType in ("Pipe", "Elbow", "Flange", "Reduct",
                                     "Tee", "Cap", "Valve", "Gasket", "Ubolt")]
        return len(pipe_objs) > 0


class CmdGenerateIsometricFull:
    """Genera isométrico de todas las tuberías del documento."""

    def GetResources(self):
        return {
            "Pixmap": __file__.rsplit("/", 1)[0]
                      + "/iconz/quetzal_isometric.svg",
            "MenuText": "Generar Isométrico (Todo el documento)",
            "ToolTip": "Genera dibujo isométrico SVG de TODA la tubería "
                       "del documento",
            "Accel": "I, F",
        }

    def Activated(self):
        from PySide import QtGui
        try:
            result = generate_isometric(use_selection=False)
            if result:
                msg = (f"✅ Isométrico general generado\n"
                       f"   Tuberías: {result['pipes']}\n"
                       f"   Fittings: {result['fittings']}\n"
                       f"   Elevaciones: {result['elevations']}\n"
                       f"   Items BOM: {result['bom_items']}\n"
                       f"   Archivo: {result['path']}")
                FreeCAD.Console.PrintMessage(msg + "\n")

                reply = QtGui.QMessageBox.question(
                    None, "Isométrico Generado",
                    f"{msg}\n\n¿Abrir el SVG en el navegador?",
                    QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
                if reply == QtGui.QMessageBox.Yes:
                    import subprocess
                    subprocess.Popen(["xdg-open", result["path"]])
        except Exception as e:
            FreeCAD.Console.PrintError(f"Error: {e}\n")

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        if not doc:
            return False
        for obj in doc.Objects:
            if (hasattr(obj, "PType")
                    and obj.PType in ("Pipe", "Elbow", "Flange")):
                return True
        return False


# ─── REGISTRO DE COMANDOS ───────────────────────────────────────────────────

def register_commands():
    """Llama a FreeCADCmd para registrar los comandos en el workbench."""
    try:
        FreeCADGui.addCommand("Quetzal_Isometric", CmdGenerateIsometric())
        FreeCADGui.addCommand("Quetzal_Isometric_Full",
                              CmdGenerateIsometricFull())
        FreeCAD.Console.PrintMessage(
            "✅ Comandos isométricos registrados: "
            "Quetzal_Isometric, Quetzal_Isometric_Full\n")
    except Exception as e:
        FreeCAD.Console.PrintWarning(
            f"No se pudieron registrar comandos isométricos: {e}\n")


# ─── MODO STANDALONE ───────────────────────────────────────────────────────

if __name__ == "__main__" and HAS_FREECAD:
    # Modo FreeCAD: ejecutar generador con argumentos
    import sys
    use_sel = "--selection" in sys.argv
    out = None
    for i, a in enumerate(sys.argv):
        if a == "--output" and i + 1 < len(sys.argv):
            out = sys.argv[i + 1]
    generate_isometric(use_selection=use_sel, output_path=out)

if __name__ == "__main__" and not HAS_FREECAD:
    # Modo standalone: generar SVG de demostración
    print("Modo standalone: generando isométrico de ejemplo...")

    demo_pts = [
        (0, 0, 0), (1000, 0, 0),
        (1000, 0, 500), (2000, 500, 500),
        (2000, 1000, 500), (3000, 1000, 0),
    ]

    svg = [_svg_header()]
    _draw_border(svg, "DEMO — ISOMÉTRICO DE EJEMPLO")

    ox, oy = PAGE_W / 2, PAGE_H / 2
    for i in range(len(demo_pts) - 1):
        p1 = iso_project(demo_pts[i])
        p2 = iso_project(demo_pts[i + 1])
        _draw_pipe_centerline(svg, p1, p2, ox, oy)
        _draw_elevation(svg, p1, demo_pts[i][2], ox, oy, f"PT{i}")

    _draw_elevation(svg, iso_project(demo_pts[-1]),
                    demo_pts[-1][2], ox, oy, f"PT{len(demo_pts)-1}")

    demo_bom = [
        {"type": "Pipe", "size": "DN100", "rating": "SCH-STD",
         "od": 114.3, "thk": 6.02, "qty": 5, "material": "API 5L Gr.B"},
        {"type": "Elbow", "size": "DN100", "rating": "SCH-STD",
         "od": 114.3, "thk": 6.02, "qty": 3, "material": "A234 WPB"},
        {"type": "Flange", "size": "DN100", "rating": "150# RF",
         "od": 114.3, "thk": 0, "qty": 2, "material": "A105"},
    ]
    _draw_bom_table(svg, demo_bom)

    svg.append(_svg_footer())
    import sys
    demo_path = "/tmp/isometric_demo.svg"
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            demo_path = sys.argv[idx + 1]
    with open(demo_path, "w") as f:
        f.write("\n".join(svg))
    print(f"\n✅ SVG de ejemplo generado: {demo_path}")
    print("   Ábrelo en cualquier navegador.")
