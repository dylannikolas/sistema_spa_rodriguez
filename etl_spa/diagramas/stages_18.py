# -*- coding: utf-8 -*-
import math, cairosvg
from PIL import Image, ImageFont
FT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
FONT, FONT_B = "DejaVu Sans", "DejaVu Sans Bold"
ROW_H, HDR_H, BOX_W, GAPY = 32, 40, 330, 90
COLX = [40 + i * 430 for i in range(5)]
HEADER, HEADER_NEW, BODY, BORDER = "#2E5B8A", "#2E7D4F", "#EAF1FA", "#1F3A5C"
PK_C, FK_C = "#B00020", "#8A5A00"
BG = {"new": "#D8F0DC", "del": "#F9D9D6", "issue": "#FCE8C8", None: None}
def C(n, k="a", s=None): return (n, k, s)

POS = {"PROVEEDOR": (2,0), "ESPECIALIDAD": (0,1), "EMPLEADO": (1,1), "PEDIDO_COMPRA": (2,1), "DETALLE_PEDIDO": (3,1), "VENTA": (4,1),
       "CLIENTE_PREFERENCIA": (0,2), "PREFERENCIA_CLIENTE": (0,2), "CLIENTE": (1,2), "USUARIO": (2,2), "ALMACEN": (3,2), "DETALLE_VENTA": (4,2),
       "PREFERENCIA": (0,3), "ESTADO_CITA": (1,3), "CITA": (2,3), "PRODUCTO": (4,3)}

def build(stage):
    T, R = {}, []
    s1, s2, s3 = stage == 1, stage == 2, stage == 3
    if stage == 0:
        T["USUARIO"] = [C("nombre","pk","issue"), C("telefono")]
        T["CLIENTE"] = [C("codigo_identificacion","pk"), C("nombre","a","issue"), C("direccion_calle"), C("direccion_ciudad"), C("usuario_nombre","fk")]
        T["PREFERENCIA_CLIENTE"] = [C("codigo_identificacion","pkfk"), C("preferencia","pk")]
        T["EMPLEADO"] = [C("codigo_empleado","pk"), C("especialidad"), C("usuario_nombre","fk")]
        T["ALMACEN"] = [C("codigo_almacen","pk"), C("usuario_nombre","fk")]
        T["PROVEEDOR"] = [C("codigo","pk"), C("nombre"), C("datos_contacto_telefono"), C("datos_contacto_correo")]
        T["PEDIDO_COMPRA"] = [C("fecha_pedido","pk","issue"), C("usuario_nombre","fk"), C("codigo_proveedor","fk")]
        T["DETALLE_PEDIDO"] = [C("fecha_pedido","pkfk"), C("codigo_producto","pkfk"), C("cantidad"), C("precio")]
        T["CITA"] = [C("numero_registro","pk"), C("fecha"), C("hora_inicio"), C("hora_fin (derivado)"), C("estado"), C("observaciones"), C("usuario_nombre","fk")]
        T["SERVICIO"] = [C("codigo_servicio","pk"), C("nombre"), C("descripcion"), C("precio"), C("duracion"), C("numero_registro","fk","issue")]
        T["PRODUCTO"] = [C("codigo","pk"), C("nombre"), C("descripcion"), C("precio_unitario"), C("stock"), C("codigo_almacen","fk"), C("codigo_servicio","fk","issue")]
        T["VENTA"] = [C("numero","pk"), C("fecha"), C("total (derivado)")]
        T["DETALLE_VENTA"] = [C("numero_venta","pkfk"), C("codigo_producto","pkfk"), C("cantidad"), C("precio")]
        R = [("CLIENTE","USUARIO"),("EMPLEADO","USUARIO"),("ALMACEN","USUARIO"),("CITA","USUARIO"),("PEDIDO_COMPRA","USUARIO"),("PEDIDO_COMPRA","PROVEEDOR"),
             ("PREFERENCIA_CLIENTE","CLIENTE"),("SERVICIO","CITA"),("PRODUCTO","SERVICIO"),("PRODUCTO","ALMACEN"),("DETALLE_PEDIDO","PEDIDO_COMPRA"),
             ("DETALLE_PEDIDO","PRODUCTO"),("DETALLE_VENTA","VENTA"),("DETALLE_VENTA","PRODUCTO")]
        pos = dict(POS); pos["SERVICIO"] = (2,4); return T, R, {k: v for k, v in pos.items() if k in T}, set()
    nw = "new" if s1 else None
    T["USUARIO"] = [C("id_usuario","pk",nw), C("nombre","a",nw), C("telefono")]
    cli = [C("codigo_cliente","pk")]
    cli += [C("nombre","a","del"), C("nombres","a","new"), C("apellidos","a","new")] if s1 else [C("nombres"), C("apellidos")]
    T["CLIENTE"] = cli + [C("calle"), C("ciudad"), C("id_usuario","fk",nw)]
    if s3: T["CLIENTE_PREFERENCIA"] = [C("codigo_cliente","pkfk"), C("preferencia","pk","del"), C("id_preferencia","pkfk","new")]
    else: T["CLIENTE_PREFERENCIA"] = [C("codigo_cliente","pkfk"), C("preferencia","pk","issue" if s2 else None)]
    if s3: T["EMPLEADO"] = [C("codigo_empleado","pk"), C("especialidad","a","del"), C("id_especialidad","fk","new"), C("id_usuario","fk")]
    else: T["EMPLEADO"] = [C("codigo_empleado","pk"), C("especialidad","a","issue" if s2 else None), C("id_usuario","fk",nw)]
    T["ALMACEN"] = [C("codigo_almacen","pk"), C("id_usuario","fk",nw)]
    T["PROVEEDOR"] = [C("codigo_proveedor","pk"), C("razon_social"), C("telefono"), C("correo")]
    T["PEDIDO_COMPRA"] = [C("id_pedido","pk",nw), C("fecha","a",nw), C("id_usuario","fk",nw), C("codigo_proveedor","fk")]
    iss, dl = ("issue" if s1 else None), ("del" if s2 else None)
    nomprod = [C("nombre_producto","a",iss or dl)] if (s1 or s2) else []
    T["DETALLE_PEDIDO"] = [C("id_pedido","pkfk",nw), C("codigo_producto","pkfk")] + nomprod + [C("cantidad"), C("precio")]
    T["DETALLE_VENTA"] = [C("numero_venta","pkfk"), C("codigo_producto","pkfk")] + nomprod + [C("cantidad"), C("precio")]
    cita = [C("numero_registro","pk"), C("fecha"), C("hora_inicio"), C("hora_fin (derivado)")]
    if s3: cita += [C("estado","a","del"), C("observaciones"), C("id_estado","fk","new"), C("id_usuario","fk")]
    else: cita += [C("estado","a","issue" if s2 else None), C("observaciones"), C("id_usuario","fk",nw)]
    T["CITA"] = cita
    pr = [C("codigo_producto","pk"), C("nombre"), C("descripcion"), C("precio_unitario"), C("stock"), C("codigo_almacen","fk")]
    if s1: pr.append(C("codigo_servicio","fk","del"))
    T["PRODUCTO"] = pr
    T["VENTA"] = [C("numero_venta","pk"), C("fecha"), C("total (derivado)")]
    cs = [C("numero_registro","pkfk"), C("codigo_servicio","pkfk")] + ([C("nombre_servicio","a",iss or dl)] if (s1 or s2) else []) + [C("precio")]
    T["CITA_SERVICIO"] = cs
    sv = [C("codigo_servicio","pk"), C("nombre"), C("descripcion"), C("precio"), C("duracion")]
    if s1: sv.append(C("numero_registro","fk","del"))
    T["SERVICIO"] = sv
    T["SERVICIO_PRODUCTO"] = [C("codigo_servicio","pkfk"), C("codigo_producto","pkfk")] + ([C("nombre_producto","a",iss or dl)] if (s1 or s2) else []) + [C("cantidad_usada")]
    new_tables = set()
    if s1: new_tables |= {"CITA_SERVICIO", "SERVICIO_PRODUCTO"}
    if s3:
        T["ESTADO_CITA"] = [C("id_estado","pk","new"), C("descripcion","a","new")]
        T["ESPECIALIDAD"] = [C("id_especialidad","pk","new"), C("nombre_especialidad","a","new")]
        T["PREFERENCIA"] = [C("id_preferencia","pk","new"), C("descripcion","a","new")]
        new_tables |= {"ESTADO_CITA", "ESPECIALIDAD", "PREFERENCIA"}
    R = [("CLIENTE","USUARIO"),("EMPLEADO","USUARIO"),("ALMACEN","USUARIO"),("CITA","USUARIO"),("PEDIDO_COMPRA","USUARIO"),("PEDIDO_COMPRA","PROVEEDOR"),
         ("CLIENTE_PREFERENCIA","CLIENTE"),("CITA_SERVICIO","CITA"),("CITA_SERVICIO","SERVICIO"),("SERVICIO_PRODUCTO","SERVICIO"),("SERVICIO_PRODUCTO","PRODUCTO"),
         ("PRODUCTO","ALMACEN"),("DETALLE_PEDIDO","PEDIDO_COMPRA"),("DETALLE_PEDIDO","PRODUCTO"),("DETALLE_VENTA","VENTA"),("DETALLE_VENTA","PRODUCTO")]
    if s3: R += [("CITA","ESTADO_CITA"),("EMPLEADO","ESPECIALIDAD"),("CLIENTE_PREFERENCIA","PREFERENCIA")]
    pos = dict(POS); pos.update({"CITA_SERVICIO": (2,4), "SERVICIO": (3,4), "SERVICIO_PRODUCTO": (4,4)})
    return T, R, {k: v for k, v in pos.items() if k in T}, new_tables

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;")

def render(stage, title, legend, out, orange_producto=False):
    tabs, R, pos, newt = build(stage)
    nrows = max(p[1] for p in pos.values()) + 1; rowh = [0] * nrows
    for n, cols in tabs.items(): rowh[pos[n][1]] = max(rowh[pos[n][1]], HDR_H + ROW_H * len(cols))
    top = 110; rowy = []; y = top
    for r in range(nrows): rowy.append(y); y += rowh[r] + GAPY
    G = {}
    for n, cols in tabs.items():
        c, r = pos[n]; h = HDR_H + ROW_H * len(cols)
        G[n] = dict(x=COLX[c], y=rowy[r], w=BOX_W, h=h, cx=COLX[c] + BOX_W / 2, cy=rowy[r] + h / 2)
    shapes, lines = [], []
    for n, cols in tabs.items():
        g = G[n]; x, y0, w, h = g["x"], g["y"], g["w"], g["h"]
        hc = HEADER_NEW if n in newt else HEADER; label = n + ("  (NUEVA)" if n in newt else "")
        shapes.append(f'<rect x="{x}" y="{y0}" width="{w}" height="{h}" fill="{BODY}" stroke="{BORDER}" stroke-width="2"/>')
        shapes.append(f'<rect x="{x}" y="{y0}" width="{w}" height="{HDR_H}" fill="{hc}" stroke="{BORDER}" stroke-width="2"/>')
        shapes.append(f'<text x="{x+w/2}" y="{y0+HDR_H/2+1}" font-family="{FONT_B}" font-size="18" font-weight="bold" text-anchor="middle" dominant-baseline="central" fill="#fff">{esc(label)}</text>')
        cy = y0 + HDR_H
        for (cn, k, st) in cols:
            if BG[st]: shapes.append(f'<rect x="{x+1}" y="{cy}" width="{w-2}" height="{ROW_H}" fill="{BG[st]}"/>')
            shapes.append(f'<line x1="{x}" y1="{cy+ROW_H}" x2="{x+w}" y2="{cy+ROW_H}" stroke="#C3D2E3" stroke-width="1"/>')
            suf = {"pk": "  (PK)", "fk": "  (FK)", "pkfk": "  (PK, FK)", "a": ""}[k]
            color = "#8E3B34" if st == "del" else (PK_C if k in ("pk", "pkfk") else (FK_C if k == "fk" else "#111"))
            ty = cy + ROW_H / 2 + 1
            shapes.append(f'<text x="{x+12}" y="{ty}" font-family="{FONT}" font-size="16" text-anchor="start" dominant-baseline="central" fill="{color}">{esc(cn+suf)}</text>')
            if k in ("pk", "pkfk"): shapes.append(f'<line x1="{x+12}" y1="{ty+10}" x2="{x+12+FT.getlength(cn):.1f}" y2="{ty+10}" stroke="{color}" stroke-width="1.4"/>')
            if st == "del": shapes.append(f'<line x1="{x+10}" y1="{ty}" x2="{x+14+FT.getlength(cn+suf):.1f}" y2="{ty}" stroke="#8E3B34" stroke-width="1.8"/>')
            cy += ROW_H
    def clip(g, ux, uy):
        hw, hh = g["w"] / 2, g["h"] / 2
        s = min(hw / abs(ux) if abs(ux) > 1e-9 else 1e9, hh / abs(uy) if abs(uy) > 1e-9 else 1e9)
        return g["cx"] + ux * s, g["cy"] + uy * s
    for child, parent in R:
        if child not in G or parent not in G: continue
        a, b = G[child], G[parent]; dx, dy = b["cx"] - a["cx"], b["cy"] - a["cy"]; L = math.hypot(dx, dy); ux, uy = dx / L, dy / L
        x1, y1 = clip(a, ux, uy); x2, y2 = clip(b, -ux, -uy)
        hot = orange_producto and parent == "PRODUCTO"; col = "#C77700" if hot else "#5B6B7C"
        lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="{2.6 if hot else 2}"/>')
        for (px, py, vx, vy, txt) in ((x1, y1, ux, uy, "N"), (x2, y2, -ux, -uy, "1")):
            nx, ny = -vy, vx; lx, ly = px + vx * 22 + nx * 16, py + vy * 22 + ny * 16
            shapes.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-family="{FONT_B}" font-size="19" font-weight="bold" text-anchor="middle" dominant-baseline="central" fill="#B00020">{txt}</text>')
    W = COLX[-1] + BOX_W + 40; H = y - GAPY + 40
    head = [f'<text x="40" y="45" font-family="{FONT_B}" font-size="28" font-weight="bold" fill="#1F3A5C">{esc(title)}</text>']
    lx = 40; ly = 80
    for (color, txt, stroke) in legend:
        head.append(f'<rect x="{lx}" y="{ly-11}" width="26" height="18" fill="{color}" stroke="{stroke}" stroke-width="1.5"/>')
        head.append(f'<text x="{lx+34}" y="{ly}" font-family="{FONT}" font-size="15" dominant-baseline="central" fill="#222">{esc(txt)}</text>'); lx += 34 + len(txt) * 8.6 + 36
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="white"/>' + "".join(lines) + "".join(shapes) + "".join(head) + '</svg>'
    cairosvg.svg2png(bytestring=svg.encode(), write_to=out, scale=1.4)
    im = Image.open(out).convert("RGB"); im.save(out); print(out, im.size)

LN = ("#D8F0DC", "Agregado o modificado en esta etapa", "#2E7D4F"); LD = ("#F9D9D6", "Eliminado en esta etapa (tachado)", "#8E3B34")
LI = ("#FCE8C8", "Problema que se corrige en la etapa siguiente", "#B7791F")
render(0, "Forma No Normalizada (0FN)", [LI], "fn0.png")
render(1, "Primera Forma Normal (1FN)", [LN, LD, LI], "fn1.png")
render(2, "Segunda Forma Normal (2FN)", [LD, LI], "fn2.png")
render(3, "Tercera Forma Normal (3FN)", [LN, LD, ("#FFFFFF", "Línea naranja: caminos hacia PRODUCTO", "#C77700")], "fn3.png", orange_producto=True)
