# -*- coding: utf-8 -*-
import csv, re, datetime as dt, openpyxl
from PIL import Image, ImageDraw, ImageFont
E = '/home/claude/etl/etl_spa/'
FM = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 17); FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 17)
FT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20); FS = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
FSB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 15)
LOG = open(E + 'log_etl.txt', encoding='utf-8').read(); DEMO = open(E + 'log_demo_cuarentena.txt', encoding='utf-8').read()
def seccion(txt, ini, fin=None):
    a = txt.index(ini); b = txt.index(fin, a + 1) if fin else len(txt); return txt[a:b].rstrip().split('\n')
def terminal(path, titulo, lineas, ancho=116):
    w = []
    for ln in lineas:
        while len(ln) > ancho: w.append(ln[:ancho]); ln = '      ' + ln[ancho:]
        w.append(ln)
    H = 66 + 24 * len(w) + 20; W = 1180; im = Image.new('RGB', (W, H), (30, 33, 40)); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 44), fill=(52, 58, 70)); d.text((18, 10), titulo, font=FT, fill=(235, 235, 235))
    for i, ln in enumerate(w):
        col = (120, 220, 140) if '[PASS]' in ln else (255, 110, 110) if ('[FAIL]' in ln or 'ERROR GRAVE' in ln) else (255, 200, 90) if ('[AVISO]' in ln or 'CUARENTENA' in ln or '[DEMO]' in ln) else (130, 190, 255) if re.match(r'(FASE|DETECCIÓN|RESULTADO|EXTRACCIÓN|TRANSFORMACIÓN)', ln) else (225, 225, 225)
        d.text((18, 58 + i * 24), ln, font=(FB if col == (130, 190, 255) else FM), fill=col)
    im.save(path); print(path, im.size)
def grid(path, titulo, filas, nfilas_titulo=0, hoja=None, header_row=None, nums=None, maxw=34):
    """Vista tipo Excel: letras de columna, números de fila, cabecera azul y pestaña de la hoja."""
    ncol = max(len(r) for r in filas); cw = []
    for j in range(ncol):
        L = max([len(str(r[j])) if j < len(r) and r[j] is not None else 0 for r in filas] + [6]); cw.append(min(maxw, L) * 9.3 + 22)
    RH = 28; X0 = 52; W = int(X0 + sum(cw) + 6); H = 40 + RH + RH * len(filas) + 44
    im = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 34), fill=(33, 115, 70)); d.text((14, 8), titulo, font=FSB, fill='white')
    y = 40; d.rectangle((0, y, W, y + RH), fill=(230, 230, 230))
    x = X0
    for j in range(ncol):
        d.text((x + cw[j] / 2 - 5, y + 6), chr(65 + j), font=FS, fill=(60, 60, 60)); d.line((x, y, x, y + RH), fill=(190, 190, 190)); x += cw[j]
    for i, r in enumerate(filas):
        y = 40 + RH + RH * i; num = nums[i] if nums else i + 1
        d.rectangle((0, y, X0, y + RH), fill=(230, 230, 230)); d.text((10, y + 6), str(num), font=FS, fill=(60, 60, 60))
        hdr = header_row is not None and i == header_row; x = X0
        for j in range(ncol):
            if hdr: d.rectangle((x, y, x + cw[j], y + RH), fill=(46, 91, 138))
            d.rectangle((x, y, x + cw[j], y + RH), outline=(215, 215, 215))
            v = r[j] if j < len(r) and r[j] is not None else ''
            resto_vacio = all((r[k] if k < len(r) else '') in ('', None) for k in range(j + 1, ncol))
            d.text((x + 6, y + 6), (str(v) if resto_vacio else str(v)[:maxw + 2]), font=(FSB if (hdr or i < nfilas_titulo) else FS), fill=('white' if hdr else (20, 20, 20))); x += cw[j]
    yb = H - 40; d.rectangle((0, yb, W, H), fill=(240, 240, 240)); d.rectangle((X0, yb, X0 + 170, H), fill='white', outline=(33, 115, 70)); d.text((X0 + 14, yb + 11), hoja or '', font=FSB, fill=(33, 115, 70))
    im.save(path); print(path, im.size)
def mostrar(col, v):
    if v is None: return ''
    if isinstance(v, dt.datetime): return v.strftime('%d/%m/%Y %H:%M') if col == 'Modificado' else v.strftime('%d/%m/%Y')
    if isinstance(v, dt.date): return v.strftime('%d/%m/%Y')
    if isinstance(v, dt.time): return v.strftime('%H:%M')
    if isinstance(v, float) or (isinstance(v, int) and col in ('Precio', 'Precio cobrado', 'Precio unit.', 'Total venta')): return f'S/ {float(v):,.2f}'
    return str(v)
def hoja_vista(libro, hoja, salida, maxw=34):
    ws = openpyxl.load_workbook(E + 'excel_sucios/' + libro, data_only=True)[hoja]
    hdr = [str(c.value) for c in ws[4]]; filas = []
    for r in range(1, ws.max_row + 1):
        filas.append([mostrar(hdr[c - 1] if r >= 4 and c <= len(hdr) else '', ws.cell(r, c).value) for c in range(1, ws.max_column + 1)])
    grid(salida, f'{libro} — Excel (origen, sin modificar)', filas, nfilas_titulo=2, hoja=hoja, header_row=3, maxw=maxw)
hoja_vista('Spa_Personal_y_Clientes.xlsx', 'Clientes', 'ev01.png')
hoja_vista('Spa_Citas.xlsx', 'Citas', 'ev02.png', maxw=19)
terminal('ev03.png', 'EXTRACCIÓN: libros Excel → CSV (salida de etl_spa.py)', seccion(LOG, 'EXTRACCIÓN', 'TRANSFORMACIÓN'))
terminal('ev04.png', 'TRANSFORMACIÓN: limpieza sin tocar la base de datos', seccion(LOG, 'TRANSFORMACIÓN', 'FASE 1'))
# antes / después: errores sembrados que el ETL corrigió (valor sucio -> valor limpio)
bit = list(csv.DictReader(open(E + 'bitacora_errores_sembrados.csv', encoding='utf-8-sig'), delimiter=';'))
pick = [('Clientes', 'Distrito', 'TIPOGRAFICO'), ('Clientes', 'Celular', 'TIPO_DATO'), ('Servicios', 'Precio', 'TIPO_DATO'), ('Servicios', 'Duracion', 'TIPO_DATO'), ('Citas', 'Fecha', 'FECHA_HORA'),
        ('Citas', 'Hora inicio', 'FECHA_HORA'), ('Citas', 'Hora fin', 'NULO'), ('Citas', 'Estado', 'NULO'), ('Citas', 'Estado', 'TIPOGRAFICO'), ('Ventas', 'Cantidad', 'NULO'), ('Ventas', 'Total venta', 'INCONSISTENCIA'),
        ('Pedidos', 'Fecha', 'NULO')]
filas = [['Hoja', 'Fila', 'Columna', 'Operación', 'Valor en el Excel', 'Valor limpio']]; vistos = set()
for h, c, t in pick:
    for b in bit:
        if (b['hoja'], b['columna'], b['tipo_error']) == (h, c, t) and (h, c, t) not in vistos:
            vistos.add((h, c, t)); filas.append([h, b['fila_excel'], c, t, b['valor_sucio'] or '(vacío)', b['valor_esperado']])
grid('ev05.png', 'Ejemplos de correcciones: valor original del Excel → valor limpio', filas, hoja='Correcciones', header_row=0, maxw=48)
# tablas limpias
def csv_grid(nombre, n):
    rows = list(csv.reader(open(E + 'csv_limpios/' + nombre + '.csv', encoding='utf-8-sig')))[:n + 1]; return rows
def dos_grids(path, a, b, n=10):
    A, B = csv_grid(a, n), csv_grid(b, n); grid('/tmp/_a.png', f'csv_limpios/{a}.csv (resultado de la transformación)', A, hoja=a, header_row=0, maxw=46); grid('/tmp/_b.png', f'csv_limpios/{b}.csv (resultado de la transformación)', B, hoja=b, header_row=0, maxw=46)
    ia, ib = Image.open('/tmp/_a.png'), Image.open('/tmp/_b.png'); W = max(ia.width, ib.width); S = Image.new('RGB', (W, ia.height + ib.height + 16), 'white'); S.paste(ia, (0, 0)); S.paste(ib, (0, ia.height + 16)); S.save(path); print(path, S.size)
dos_grids('ev06.png', 'cita', 'producto')
terminal('ev07.png', 'FASES 1 y 2: conexión, preparación del destino y validación de los CSV', seccion(LOG, 'FASE 1', 'FASE 3'))
terminal('ev08.png', 'FASE 3 con cuarentena (prueba con 2 filas inválidas agregadas a propósito)', seccion(DEMO, 'FASE 3', 'FASE 4'))
f34 = seccion(LOG, 'FASE 3', 'FASE 4'); f4 = seccion(LOG, 'FASE 4', 'FASE 5'); cortar = next(i for i, l in enumerate(f4) if 'contenido idéntico' in l)
terminal('ev09.png', 'FASE 3 (carga) y FASE 4 (verificación de filas)', f34 + [''] + f4[:cortar])
terminal('ev10.png', 'FASE 4 (contenido, huérfanas y datos derivados)', [f4[0]] + f4[cortar:])
terminal('ev11.png', 'FASES 5 y 6: reglas de negocio, pruebas negativas, detección y resultado', seccion(LOG, 'FASE 5'))
