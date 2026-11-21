# -*- coding: utf-8 -*-
import cairosvg, textwrap
from PIL import Image
FONT = "DejaVu Sans"
COLW, NODE_W, GAP = 420, 370, 58
COL = {"start": ("#F26B6B", "#B84A4A", "#fff"), "end_ok": ("#2E7D4F", "#1F5A37", "#fff"), "end_err": ("#B94A48", "#7E2B2A", "#fff"),
       "proc": ("#FFF2DC", "#8A6A3A", "#222"), "dec": ("#FFD28A", "#8A6A3A", "#222"), "note": ("#E3F0FA", "#2E5B8A", "#222")}

def wrap(t, n): return textwrap.wrap(t, n, break_long_words=False) or [""]
def render(name, nodes, edges, title=None):
    title = None          # el Word ya trae el encabezado de cada diagrama
    G = {}
    for nid, (kind, text, c, r) in nodes.items():
        n = 24 if kind == "dec" else 36
        lines = wrap(text, n)
        h = max(46, len(lines) * 19 + 28) if kind != "dec" else max(112, len(lines) * 19 + 70)
        if kind in ("start", "end_ok", "end_err"): h = max(46, len(lines) * 19 + 26)
        G[nid] = dict(kind=kind, lines=lines, c=c, r=r, h=h, w=NODE_W if kind != "dec" else NODE_W)
    nrows = max(g["r"] for g in G.values()) + 1
    rowh = [max([g["h"] for g in G.values() if g["r"] == r] or [0]) for r in range(nrows)]
    top = 90 if title else 30; rowy, y = [], top
    for r in range(nrows): rowy.append(y + rowh[r] / 2); y += rowh[r] + GAP
    for g in G.values(): g["cx"] = 40 + NODE_W / 2 + g["c"] * COLW; g["cy"] = rowy[g["r"]]
    maxc = max(g["c"] for g in G.values()); maxoff = max([e[4] for e in edges if e[3] == "loopr" and len(e) > 4] + [0]); W = max(40 + NODE_W + maxc * COLW + 80, 40 + NODE_W + maxc * COLW + 28 + maxoff + 50); H = y - GAP + 40
    S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="white"/>',
         '<defs><marker id="ar" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#333"/></marker></defs>']
    if title: S.append(f'<text x="40" y="45" font-family="{FONT}" font-size="26" font-weight="bold" fill="#1F3A5C">{title}</text>')
    def anc(g, side):
        return {"t": (g["cx"], g["cy"] - g["h"] / 2), "b": (g["cx"], g["cy"] + g["h"] / 2), "l": (g["cx"] - g["w"] / 2, g["cy"]), "r": (g["cx"] + g["w"] / 2, g["cy"])}[side]
    rightmost = max(g["cx"] + g["w"] / 2 for g in G.values())
    for e in edges:
        a, b, lab, route = e[0], e[1], e[2], e[3]; A, B = G[a], G[b]; pts = []
        if route == "v": pts = [anc(A, "b"), anc(B, "t")]
        elif route == "h":
            sa, sb = ("r", "l") if B["cx"] > A["cx"] else ("l", "r"); pts = [anc(A, sa), anc(B, sb)]
        elif route == "hv":
            sa = "r" if B["cx"] > A["cx"] else "l"; p = anc(A, sa); pts = [p, (B["cx"], p[1]), anc(B, "t" if B["cy"] > A["cy"] else "b")]
        elif route == "vh":
            p = anc(A, "b"); sb = "l" if B["cx"] > A["cx"] else "r"; pts = [p, (p[0], B["cy"]), anc(B, sb)]
        elif route == "loopr":                                  # sale por la derecha, baja y entra por la derecha
            p = anc(A, "r"); q = anc(B, "r"); ox = rightmost + 28 + (e[4] if len(e) > 4 else 0); pts = [p, (ox, p[1]), (ox, q[1]), q]
        elif route == "loopl":                                  # sale por la izquierda, sube/baja y entra por la izquierda
            p = anc(A, "l"); q = anc(B, "l"); ox = min(g["cx"] - g["w"] / 2 for g in G.values()) - 28 - (e[4] if len(e) > 4 else 0); pts = [p, (ox, p[1]), (ox, q[1]), q]
        elif route == "up":                                      # vuelve hacia arriba por la derecha
            p = anc(A, "t"); q = anc(B, "r"); pts = [p, (p[0], q[1]), q]
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        S.append(f'<path d="{d}" fill="none" stroke="#333" stroke-width="2" marker-end="url(#ar)"/>')
        if lab:
            x0, y0 = pts[0]; x1, y1 = pts[1]
            lx, ly = (x0 + (x1 - x0) * 0.25, y0 + (y1 - y0) * 0.25 + (-12 if y1 == y0 else 0)); lx += 14 if x1 == x0 else 0
            if x1 == x0: ly = y0 + 16
            S.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-family="{FONT}" font-size="15" font-weight="bold" fill="#111">{lab}</text>')
    for g in G.values():
        fill, stroke, tc = COL[g["kind"]]; x, y0, w, h = g["cx"] - g["w"] / 2, g["cy"] - g["h"] / 2, g["w"], g["h"]
        if g["kind"] == "dec": S.append(f'<polygon points="{g["cx"]},{y0} {x+w},{g["cy"]} {g["cx"]},{y0+h} {x},{g["cy"]}" fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>')
        elif g["kind"] in ("start", "end_ok", "end_err"): S.append(f'<rect x="{x}" y="{y0}" width="{w}" height="{h}" rx="{h/2}" fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>')
        else: S.append(f'<rect x="{x}" y="{y0}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>')
        n = len(g["lines"]); ty = g["cy"] - (n - 1) * 9.5
        for i, ln in enumerate(g["lines"]):
            S.append(f'<text x="{g["cx"]}" y="{ty + i * 19:.1f}" font-family="{FONT}" font-size="15" text-anchor="middle" dominant-baseline="central" fill="{tc}">{ln.replace("&","&amp;").replace("<","&lt;")}</text>')
    S.append('</svg>'); cairosvg.svg2png(bytestring="".join(S).encode(), write_to=name, scale=1.5)
    from PIL import ImageChops
    im = Image.open(name).convert("RGB"); bb = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
    im = im.crop((max(bb[0] - 30, 0), max(bb[1] - 30, 0), min(bb[2] + 30, im.width), min(bb[3] + 30, im.height))); im.save(name); print(name, im.size)


# ------------------------------------------------------------------ 1. extracción (origen: libros Excel)
render("flujo_extraccion.png", {
 "s": ("start", "INICIO", 1, 0), "p1": ("proc", "Abrir cada libro Excel (.xlsx) del spa y ubicar sus hojas de datos (las hojas de apoyo se ignoran)", 1, 1),
 "d1": ("dec", "¿La hoja tiene estructura tabular directa?", 1, 2),
 "a1": ("proc", "Descombinar celdas y ubicar la cabecera real (omitir títulos y filas desplazadas)", 2, 2), "a2": ("proc", "Delimitar el rango de filas y columnas válidas", 2, 3),
 "d2": ("dec", "¿El total de filas y columnas extraídas coincide con la hoja original?", 1, 4),
 "p2": ("proc", "Convertir cada hoja a CSV (UTF-8) sin alterar sus valores → csv_extraidos", 1, 5), "p3": ("proc", "Leer los archivos CSV extraídos", 1, 6), "e": ("end_ok", "FIN · listos para transformar", 1, 7)},
 [("s", "p1", "", "v"), ("p1", "d1", "", "v"), ("d1", "a1", "No", "h"), ("a1", "a2", "", "v"), ("a2", "d2", "", "vh"), ("d1", "d2", "Sí", "v"), ("d2", "d1", "No", "loopl", 0),
  ("d2", "p2", "Sí", "v"), ("p2", "p3", "", "v"), ("p3", "e", "", "v")])
# ------------------------------------------------------------------ 2. nulos
render("flujo_nulos.png", {
 "s": ("start", "INICIO", 1, 0), "d1": ("dec", "¿La fila está vacía o es un título / fila de resumen?", 1, 1), "a1": ("proc", "Eliminar la fila: no es dato de negocio", 2, 1),
 "d2": ("dec", "¿El dato se puede recuperar de otra columna, fila o archivo?", 1, 2),
 "a2": ("proc", "Recuperarlo (hora fin = inicio + duración; estado desde observaciones; fecha desde otra línea del pedido)", 2, 2),
 "d3": ("dec", "¿El campo es obligatorio en la base?", 1, 3), "a3": ("proc", "Revisión manual con el dueño (no se imputa media, mediana ni moda); si sigue vacío, cuarentena", 2, 3),
 "a4": ("proc", "Dejar NULL: el dato opcional no se inventa", 1, 4), "m": ("proc", "Valores nulos tratados", 1, 5), "e": ("end_ok", "FIN", 1, 6)},
 [("s", "d1", "", "v"), ("d1", "a1", "Sí", "h"), ("d1", "d2", "No", "v"), ("d2", "a2", "Sí", "h"), ("d2", "d3", "No", "v"), ("d3", "a3", "Sí", "h"), ("d3", "a4", "No", "v"),
  ("a1", "m", "", "loopr", 0), ("a2", "m", "", "loopr", 0), ("a3", "m", "", "loopr", 0), ("a4", "m", "", "v"), ("m", "e", "", "v")])
# ------------------------------------------------------------------ 3. duplicados
render("flujo_duplicados.png", {
 "s": ("start", "INICIO", 1, 0), "p1": ("proc", "Cargar las hojas extraídas en memoria (zona de paso): primero se transforma, después se carga a la base", 1, 1),
 "p2": ("proc", "Definir la clave de cada hoja (ej.: N° de cita + servicio; nombre ya normalizado)", 1, 2), "d1": ("dec", "¿Hay registros con la misma clave?", 1, 3),
 "d2": ("dec", "¿Qué criterio de prioridad aplica?", 1, 4),
 "a": ("proc", "Modificado más reciente (citas)", 0, 5), "b": ("proc", "Registro más completo (clientes)", 1, 5), "c": ("proc", "Primera ocurrencia (copias exactas)", 2, 5),
 "p3": ("proc", "Conservar un solo registro y eliminar los demás (queda anotado en el log)", 1, 6), "e": ("end_ok", "FIN · datos únicos", 1, 7)},
 [("s", "p1", "", "v"), ("p1", "p2", "", "v"), ("p2", "d1", "", "v"), ("d1", "d2", "Sí", "v"), ("d1", "p3", "No", "loopr", 0), ("d2", "a", "", "hv"), ("d2", "b", "", "v"), ("d2", "c", "", "hv"),
  ("a", "p3", "", "vh"), ("b", "p3", "", "v"), ("c", "p3", "", "vh"), ("p3", "e", "", "v")])
# ------------------------------------------------------------------ 4. tipográficos
render("flujo_tipograficos.png", {
 "s": ("start", "INICIO", 1, 0), "p1": ("proc", "Leer el texto de la celda y limpiarlo solo para comparar: espacios, mayúsculas y tildes", 1, 1),
 "d1": ("dec", "¿Coincide con un valor del diccionario de valores válidos?", 1, 2),
 "d2": ("dec", "¿Es un alias conocido o su similitud es ≥ 88 %?", 1, 3), "a1": ("proc", "Reemplazar por el valor oficial del diccionario (con sus tildes y eñes)", 2, 3),
 "a2": ("proc", "Marcar para revisión manual (no se carga)", 1, 4), "m": ("proc", "Actualizar el valor en el CSV limpio (siempre el valor oficial)", 1, 5), "e": ("end_ok", "FIN", 1, 6)},
 [("s", "p1", "", "v"), ("p1", "d1", "", "v"), ("d1", "d2", "No", "v"), ("d1", "m", "Sí", "loopr", 70), ("d2", "a1", "Sí", "h"), ("d2", "a2", "No", "v"),
  ("a1", "m", "", "loopr", 0), ("a2", "m", "", "v"), ("m", "e", "", "v")])
# ------------------------------------------------------------------ 5. tipo de dato
render("flujo_tipo_dato.png", {
 "s": ("start", "INICIO", 1, 0), "p1": ("proc", "Leer la celda y su tipo destino (DECIMAL en soles, INT, minutos, teléfono de 9 dígitos)", 1, 1),
 "d1": ("dec", "¿La celda ya es un número de Excel o se puede convertir directamente?", 1, 2),
 "p2": ("proc", "Quitar el símbolo S/, las unidades (und, min, '), los espacios y separadores; la coma decimal pasa a punto", 1, 3), "d2": ("dec", "¿La conversión ahora es exitosa?", 1, 4),
 "a": ("end_err", "No convertible: revisión manual; si el campo es opcional queda NULL y, si es obligatorio, va a cuarentena", 2, 4),
 "m": ("proc", "Asignar el tipo de dato a la columna (los precios se mantienen en soles)", 1, 5), "e": ("end_ok", "FIN", 1, 6)},
 [("s", "p1", "", "v"), ("p1", "d1", "", "v"), ("d1", "p2", "No", "v"), ("d1", "m", "Sí", "loopr", 70), ("p2", "d2", "", "v"), ("d2", "m", "Sí", "v"), ("d2", "a", "No", "h"), ("m", "e", "", "v")])
# ------------------------------------------------------------------ 6. fecha y hora
render("flujo_fecha_hora.png", {
 "s": ("start", "INICIO", 1, 0), "p1": ("proc", "Leer la celda de fecha u hora", 1, 1), "d1": ("dec", "¿Es una fecha u hora nativa de Excel?", 1, 2),
 "d2": ("dec", "¿Está en dd/mm/aaaa o en HH:MM de 24 horas?", 1, 3),
 "p2": ("proc", "Reconocer formatos locales: 5/10/26, 06-10-2026, 7.10.2026, «5 de octubre de 2026», 9:00 am, 11h00", 1, 4),
 "p3": ("proc", "Interpretar con el día primero y la hora de Lima (UTC−5); sin conversión de zona horaria", 1, 5),
 "d3": ("dec", "¿La fecha u hora es válida?", 1, 6), "a": ("proc", "Revisión manual del valor", 2, 6),
 "p4": ("proc", "Guardar como DATE y TIME de MySQL (AAAA-MM-DD y HH:MM:SS); en los documentos se muestra dd/mm/aaaa", 1, 7),
 "p5": ("proc", "Derivar hora_fin = hora_inicio + duración de los servicios de la cita", 1, 8), "e": ("end_ok", "FIN", 1, 9)},
 [("s", "p1", "", "v"), ("p1", "d1", "", "v"), ("d1", "d2", "No", "v"), ("d1", "p4", "Sí", "loopr", 70), ("d2", "p2", "No", "v"), ("d2", "p4", "Sí", "loopr", 0), ("p2", "p3", "", "v"),
  ("p3", "d3", "", "v"), ("d3", "p4", "Sí", "v"), ("d3", "a", "No", "h"), ("p4", "p5", "", "v"), ("p5", "e", "", "v")])
# ------------------------------------------------------------------ 7. carga (6 fases), en dos partes
render("flujo_carga_1.png", {
 "s": ("start", "INICIO", 1, 0), "p0": ("proc", "Leer la configuración del archivo .env (host, puerto, usuario, contraseña)", 1, 1),
 "p1": ("proc", "FASE 1 · Conectar al servidor y preparar el destino", 1, 2), "d1": ("dec", "¿Conexión exitosa y versión ≥ MySQL 8.0.16 (MariaDB ≥ 10.2.1)?", 1, 3),
 "e1": ("end_err", "Detener: informar el error de conexión o de versión (los CHECK no se aplicarían)", 2, 3),
 "d2": ("dec", "¿Existen las 18 tablas del modelo físico?", 1, 4), "a": ("proc", "Crear la estructura con spa_rodriguez.sql (sin datos)", 2, 4),
 "p2": ("proc", "Preparar el destino: quitar los triggers de stock y vaciar las tablas (la estructura se conserva)", 1, 5),
 "p3": ("proc", "FASE 2 · Validar los CSV transformados: existen, UTF-8, encabezados = columnas, tipos, obligatorios y claves sin repetir", 1, 6),
 "d3": ("dec", "¿Archivos válidos?", 1, 7), "e2": ("end_err", "Reportar archivo, fila y motivo. No cargar nada.", 2, 7),
 "c": ("end_ok", "Continúa en la Parte 2 · FASE 3", 1, 8)},
 [("s", "p0", "", "v"), ("p0", "p1", "", "v"), ("p1", "d1", "", "v"), ("d1", "e1", "No", "h"), ("d1", "d2", "Sí", "v"), ("d2", "a", "No", "h"), ("d2", "p2", "Sí", "v"), ("a", "p2", "", "vh"),
  ("p2", "p3", "", "v"), ("p3", "d3", "", "v"), ("d3", "e2", "No", "h"), ("d3", "c", "Sí", "v")])
render("flujo_carga_2.png", {
 "s": ("start", "Viene de la Parte 1 · CSV válidos", 1, 0),
 "p4": ("proc", "FASE 3 · Tomar la siguiente tabla (orden de llaves foráneas) e insertar sus filas por lotes", 1, 1), "q": ("note", "cuarentena.csv: filas rechazadas y su motivo", 2, 1),
 "d4": ("dec", "¿Error grave?", 1, 2), "e3": ("end_err", "ROLLBACK y detener: registrar el error", 2, 2),
 "d5": ("dec", "¿Quedan más tablas por cargar?", 1, 3), "p5": ("proc", "COMMIT y volver a crear los triggers de stock", 1, 4),
 "p6": ("proc", "FASE 4 · Verificar: filas leídas = insertadas + rechazadas; contenido = esperado; huérfanas = 0; total, hora_fin y stock final", 1, 5),
 "p7": ("proc", "FASE 5 · Pruebas de reglas de negocio y pruebas negativas con ROLLBACK (CHECK, FK, UNIQUE, trigger de stock)", 1, 6),
 "p8": ("proc", "FASE 6 · Reporte y evidencias: reporte_etl.md, log_etl.txt, cuarentena.csv y capturas", 1, 7),
 "d6": ("dec", "¿Todas las pruebas críticas en PASS?", 1, 8), "e4": ("end_err", "FIN con error (código de salida ≠ 0)", 2, 8), "e": ("end_ok", "FIN exitoso (código de salida 0)", 1, 9)},
 [("s", "p4", "", "v"), ("p4", "q", "", "h"), ("p4", "d4", "", "v"), ("d4", "e3", "Sí", "h"), ("d4", "d5", "No", "v"), ("d5", "p4", "Sí", "loopl", 0), ("d5", "p5", "No", "v"),
  ("p5", "p6", "", "v"), ("p6", "p7", "", "v"), ("p7", "p8", "", "v"), ("p8", "d6", "", "v"), ("d6", "e4", "No", "h"), ("d6", "e", "Sí", "v")])
