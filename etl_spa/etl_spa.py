# -*- coding: utf-8 -*-
"""
ETL del Salón Spa Rodríguez — los datos están originalmente en libros Excel (.xlsx).
  Extracción:     libros .xlsx  ->  csv_extraidos/ (una hoja = un CSV, sin alterar los valores)
  Transformación: csv_extraidos/ -> csv_limpios/ (18 tablas del modelo), sin tocar la base de datos
  Carga (6 fases): conexión y preparación -> validar CSV -> cargar con cuarentena -> verificar -> reglas de negocio -> reporte
Uso:  python etl_spa.py [--demo-cuarentena]
Conexión: archivo .env o variables DB_HOST, DB_PORT, DB_USER, DB_PASSWORD.
Salida: csv_extraidos/, csv_limpios/, cuarentena.csv, reporte_etl.md, log_etl.txt. Código de salida 0 = pruebas críticas en PASS.
"""
import csv, os, re, sys, time, unicodedata, difflib, datetime as dt
from decimal import Decimal, InvalidOperation
from collections import Counter, OrderedDict
import openpyxl, pymysql

BASE = os.path.dirname(os.path.abspath(__file__))
XLS, EXT, DIC, OUT, ESP = (os.path.join(BASE, d) for d in ('excel_sucios', 'csv_extraidos', 'diccionarios', 'csv_limpios', 'esperado'))
for d in (EXT, OUT): os.makedirs(d, exist_ok=True)
DBNAME = 'spa_rodriguez'
LOGL, RES = [], []
def say(msg=''):
    print(msg); LOGL.append(msg)
def chk(fase, prueba, ok, det='', critica=True):
    r = 'PASS' if ok else ('FAIL' if critica else 'AVISO')
    RES.append((fase, prueba, r, det)); say(f'  [{r}] {prueba}' + (f'  {det}' if det else ''))

def cfg():
    env = {}
    p = os.path.join(BASE, '.env')
    if os.path.exists(p):
        for ln in open(p, encoding='utf-8'):
            if '=' in ln and not ln.strip().startswith('#'):
                k, v = ln.strip().split('=', 1); env[k.strip()] = v.strip()
    g = lambda k, d: os.environ.get(k, env.get(k, d))
    return dict(host=g('DB_HOST', 'localhost'), port=int(g('DB_PORT', '3306')), user=g('DB_USER', 'root'), password=g('DB_PASSWORD', ''))

# ================================================================== EXTRACCIÓN (Excel -> CSV)
SHEETS = OrderedDict([
    ('Personal', ('Spa_Personal_y_Clientes.xlsx', ['Nombre', 'Celular', 'Especialidad', 'Funcion'])),
    ('Almacenes', ('Spa_Personal_y_Clientes.xlsx', ['Almacen', 'Responsable'])),
    ('Clientes', ('Spa_Personal_y_Clientes.xlsx', ['Cliente', 'Celular', 'Direccion', 'Distrito', 'Preferencias', 'Atendido por'])),
    ('Servicios', ('Spa_Catalogo.xlsx', ['Servicio', 'Descripcion', 'Precio', 'Duracion'])),
    ('Productos', ('Spa_Catalogo.xlsx', ['Producto', 'Presentacion', 'Precio', 'Stock', 'Almacen'])),
    ('Insumos por servicio', ('Spa_Catalogo.xlsx', ['Servicio', 'Producto', 'Cantidad usada'])),
    ('Proveedores', ('Spa_Catalogo.xlsx', ['Razon social', 'Telefono', 'Correo'])),
    ('Citas', ('Spa_Citas.xlsx', ['N° cita', 'Fecha', 'Hora inicio', 'Hora fin', 'Cliente', 'Servicio', 'Precio cobrado', 'Estado', 'Registrada por', 'Observaciones', 'Modificado'])),
    ('Ventas', ('Spa_Ventas_y_Pedidos.xlsx', ['N° venta', 'Fecha', 'Producto', 'Cantidad', 'Precio unit.', 'Total venta'])),
    ('Pedidos', ('Spa_Ventas_y_Pedidos.xlsx', ['N° pedido', 'Fecha', 'Proveedor', 'Producto', 'Cantidad', 'Precio unit.', 'Registrado por']))])
DATECOLS, TIMECOLS, DTCOLS = {'Fecha'}, {'Hora inicio', 'Hora fin'}, {'Modificado'}
MONEYCOLS = {'Precio', 'Precio cobrado', 'Precio unit.', 'Total venta'}
INTCOLS = {'Stock', 'Cantidad', 'Cantidad usada', 'Duracion', 'N° cita', 'N° venta', 'N° pedido'}
def canon(col, v):
    """Celda de Excel -> texto. Los valores nativos (fecha, hora, número) quedan en su forma base; el texto sucio no se toca."""
    if v is None: return ''
    if isinstance(v, dt.datetime): return v.strftime('%d/%m/%Y %H:%M') if col in DTCOLS else v.strftime('%d/%m/%Y')
    if isinstance(v, dt.date): return v.strftime('%d/%m/%Y')
    if isinstance(v, dt.time): return v.strftime('%H:%M')
    if isinstance(v, (int, float)):
        if col in MONEYCOLS: return f'{float(v):.2f}'
        if col in INTCOLS: return str(int(v))
        return str(v)
    return str(v)

def extraer():
    say('EXTRACCIÓN · Leer los libros Excel (.xlsx) y convertir cada hoja a CSV')
    for libro in OrderedDict.fromkeys(l for l, _ in SHEETS.values()):
        wb = openpyxl.load_workbook(os.path.join(XLS, libro), data_only=True)
        esperadas = [s for s, (l, _) in SHEETS.items() if l == libro]
        say(f'  Libro {libro}: hojas {[ws.title for ws in wb]}')
        for ws in wb:
            if ws.title not in esperadas: say(f'    · hoja "{ws.title}" ignorada (hoja de apoyo, no contiene datos del modelo)'); continue
            headers = SHEETS[ws.title][1]
            for rng in list(ws.merged_cells.ranges): ws.unmerge_cells(str(rng))                 # celdas combinadas -> separadas
            hrow = next((r for r in range(1, 16) if set(headers) <= {str(c.value).strip() for c in ws[r] if c.value is not None}), None)
            if hrow is None: chk('EXT', f'{ws.title}: se encontró la cabecera', False); continue
            col = {str(c.value).strip(): c.column for c in ws[hrow] if c.value is not None}
            filas = [[r] + [canon(h, ws.cell(r, col[h]).value) for h in headers] for r in range(hrow + 1, ws.max_row + 1)]
            with open(os.path.join(EXT, ws.title + '.csv'), 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f); w.writerow(['fila_excel'] + headers); w.writerows(filas)
            chk('EXT', f'{ws.title}: cabecera en la fila {hrow}; {len(filas)} filas × {len(headers)} columnas extraídas = {ws.max_row - hrow} × {len(headers)} de la hoja',
                len(filas) == ws.max_row - hrow)

# --------------------------------------------------------------- utilidades
CORR, REVISION, STAT, QUIET = [], [], {}, [False]
def log(arch, ln, col, tipo, sucio, limpio):
    if not QUIET[0]: CORR.append((arch, ln, col, tipo, sucio, str(limpio) if limpio is not None else 'NULL'))

def key(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower().replace('.', '')
    return ' '.join(s.split())
def nz(s):
    s = unicodedata.normalize('NFKD', s or '')
    return ' '.join(''.join(c for c in s if not unicodedata.combining(c)).lower().split())

class Dic:
    def __init__(self, name):
        self.pool, self.valid = {}, []
        for r in csv.DictReader(open(os.path.join(DIC, name), encoding='utf-8-sig'), delimiter=';'):
            v = r['valor_valido']; self.pool[key(v)] = v; self.valid.append(v)
            for a in filter(None, r['alias_conocidos'].split('|')): self.pool[key(a)] = v
    def match(self, raw):
        k = key(raw)
        if k in self.pool: return self.pool[k]
        m = difflib.get_close_matches(k, list(self.pool), n=1, cutoff=0.88)
        return self.pool[m[0]] if m else None
D = {n: Dic(n + '.csv') for n in ('usuarios', 'estados_cita', 'especialidades', 'distritos', 'servicios', 'productos', 'proveedores', 'almacenes', 'preferencias', 'clientes')}

MESES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9,
         'octubre': 10, 'noviembre': 11, 'diciembre': 12, 'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'ago': 8,
         'sep': 9, 'set': 9, 'oct': 10, 'nov': 11, 'dic': 12}
def parse_date(raw):                       # día primero (realidad local), nunca mes/día
    t = nz(raw)
    m = re.fullmatch(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2}|\d{4})', t)
    if m:
        d, mo, y = int(m[1]), int(m[2]), int(m[3]); y = y + 2000 if y < 100 else y
    else:
        m = re.fullmatch(r'(\d{1,2}) (?:de )?([a-z]+)(?: de)? (\d{4})', t)
        if not m or m[2] not in MESES: return None
        d, mo, y = int(m[1]), MESES[m[2]], int(m[3])
    try: return dt.date(y, mo, d)
    except ValueError: return None
def parse_time(raw):                       # 24 h, hora de Lima; admite "9:00 am", "11h00", "4:00 p. m."
    t = nz(raw).replace('.', '').replace(' ', '')
    m = re.fullmatch(r'(\d{1,2})[:h](\d{2})(am|pm)?', t)
    if not m: return None
    h, mi = int(m[1]), int(m[2])
    if m[3] == 'pm' and h < 12: h += 12
    if m[3] == 'am' and h == 12: h = 0
    return dt.time(h, mi) if h < 24 and mi < 60 else None
def parse_money(raw):                      # soles: solo se quita el símbolo (sin conversión de moneda)
    t = raw.upper().replace('S/.', '').replace('S/', '').replace(' ', '')
    if re.fullmatch(r'\d+,\d{1,2}', t): t = t.replace(',', '.')
    elif ',' in t and '.' in t: t = t.replace(',', '')
    try: return Decimal(t).quantize(Decimal('0.01'))
    except InvalidOperation: return None
def parse_int(raw):
    m = re.match(r'\s*(\d+)(?:[.,]0+)?(?!\d)', raw); return int(m[1]) if m else None
def parse_dur(raw):
    t = nz(raw); h = re.search(r'(\d+)\s*h', t); mi = re.search(r"(\d+)\s*(?:min|minutos|')", t)
    if h or mi: return (int(h[1]) * 60 if h else 0) + (int(mi[1]) if mi else 0)
    return int(t) if t.isdigit() else None
def parse_phone(raw):
    d = re.sub(r'\D', '', raw)
    if len(d) == 11 and d.startswith('51'): d = d[2:]
    return d if len(d) == 9 else None
def add_min(t, m): return (dt.datetime.combine(dt.date(2000, 1, 1), t) + dt.timedelta(minutes=m)).time()

# ---- celdas: devuelven el valor limpio y registran cada corrección
def c_dic(a, ln, col, raw, dic, base=None):
    if not raw.strip(): log(a, ln, col, 'NULO', raw, None); return None
    v = D[dic].match(raw)
    if v is None: REVISION.append((a, ln, col, raw)); return None
    if raw != (base(v) if base else v): log(a, ln, col, 'TIPOGRAFICO', raw, v)
    return v
def c_money(a, ln, col, raw):
    if not raw.strip(): log(a, ln, col, 'NULO', raw, None); return None
    v = parse_money(raw)
    if v is None: REVISION.append((a, ln, col, raw)); return None
    if not re.fullmatch(r'\d+\.\d{2}', raw): log(a, ln, col, 'TIPO_DATO', raw, v)
    return v
def c_int(a, ln, col, raw):
    if not raw.strip(): log(a, ln, col, 'NULO', raw, None); return None
    v = parse_int(raw)
    if v is None: REVISION.append((a, ln, col, raw)); return None
    if not re.fullmatch(r'\d+', raw): log(a, ln, col, 'TIPO_DATO', raw, v)
    return v
def c_dur(a, ln, col, raw):
    v = parse_dur(raw)
    if v is None: REVISION.append((a, ln, col, raw)); return None
    if not re.fullmatch(r'\d+', raw): log(a, ln, col, 'TIPO_DATO', raw, v)
    return v
def c_phone(a, ln, col, raw):
    if not raw.strip(): log(a, ln, col, 'NULO', raw, None); return None
    v = parse_phone(raw)
    if v is None: log(a, ln, col, 'TIPO_DATO', raw, None); return None       # inválido: NULL, no se inventa
    if not re.fullmatch(r'\d{9}', raw): log(a, ln, col, 'TIPO_DATO', raw, v)
    return v
def c_date(a, ln, col, raw):
    if not raw.strip(): log(a, ln, col, 'NULO', raw, None); return None
    v = parse_date(raw)
    if v is None: REVISION.append((a, ln, col, raw)); return None
    if not re.fullmatch(r'\d{2}/\d{2}/\d{4}', raw): log(a, ln, col, 'FECHA_HORA', raw, v.isoformat())
    return v
def c_time(a, ln, col, raw):
    if not raw.strip(): log(a, ln, col, 'NULO', raw, None); return None
    v = parse_time(raw)
    if v is None: REVISION.append((a, ln, col, raw)); return None
    if not re.fullmatch(r'\d{2}:\d{2}', raw): log(a, ln, col, 'FECHA_HORA', raw, v.strftime('%H:%M:%S'))
    return v
def c_text(a, ln, col, raw, lower=False):
    if not raw.strip(): log(a, ln, col, 'NULO', raw, None); return None
    v = ' '.join(raw.split()); v = v.lower() if lower else v
    if v != raw: log(a, ln, col, 'TIPOGRAFICO', raw, v)
    return v

# ---- lectura de las hojas ya extraídas de Excel
def read(name):
    with open(os.path.join(EXT, name + '.csv'), encoding='utf-8-sig', newline='') as f:
        rows = [(int(r.pop('fila_excel')), r) for r in csv.DictReader(f)]
    STAT[name] = Counter(leidas=len(rows)); return rows
def drop_noise(name, rows):
    keep = []
    for ln, r in rows:
        v = [x.strip() for x in r.values()]
        if not any(v): log(name, ln, '(fila completa)', 'NULO', 'fila vacía', 'eliminada'); STAT[name]['vacias'] += 1
        elif v[0].lower().startswith('total') and not any(v[1:]): log(name, ln, '(fila completa)', 'NULO', v[0], 'eliminada'); STAT[name]['resumen'] += 1
        else: keep.append((ln, r))
    STAT[name]['utiles'] = len(keep)
    return keep
def dedupe(name, rows, keyf, pick=None):
    groups = OrderedDict()
    for it in rows: groups.setdefault(keyf(it[1]), []).append(it)
    out = []
    for k, g in groups.items():
        win = pick(g) if (pick and len(g) > 1) else g[0]
        for it in g:
            if it is win: continue
            log(name, it[0], '(fila completa)', 'DUPLICADO', f'repite la fila {win[0]}', 'eliminada'); STAT[name]['duplicados'] += 1
            for col, val in it[1].items():                       # nulo del descartado, recuperado por el registro completo
                if not val.strip() and win[1][col].strip() and col != 'Observaciones': log(name, it[0], col, 'NULO', val, win[1][col])
        out.append(win)
    out.sort(key=lambda x: x[0]); STAT[name]['utiles'] = len(out); return out
def kdic(col, dic):
    return lambda r: (D[dic].match(r[col]) or key(r[col]))

# ============================================================ TRANSFORMACIÓN
T = OrderedDict()
def transformar():
    a = 'Personal'; rows = dedupe(a, drop_noise(a, read(a)), kdic('Nombre', 'usuarios'))
    usuarios, esp, emp, uid = [], [], [], {}
    for ln, r in rows:
        nombre = c_dic(a, ln, 'Nombre', r['Nombre'], 'usuarios'); tel = c_phone(a, ln, 'Celular', r['Celular'])
        e = c_dic(a, ln, 'Especialidad', r['Especialidad'], 'especialidades')
        uid[nombre] = len(usuarios) + 1; usuarios.append((uid[nombre], nombre, tel))
        if e:
            if e not in esp: esp.append(e)
            emp.append((len(emp) + 1, esp.index(e) + 1, uid[nombre]))
    T['usuario'] = usuarios; T['especialidad'] = [(i + 1, e) for i, e in enumerate(esp)]; T['empleado'] = emp

    a = 'Almacenes'; rows = drop_noise(a, read(a)); alm, aid = [], {}
    for ln, r in rows:
        n = c_dic(a, ln, 'Almacen', r['Almacen'], 'almacenes'); u = c_dic(a, ln, 'Responsable', r['Responsable'], 'usuarios')
        aid[n] = len(alm) + 1; alm.append((aid[n], uid[u]))
    T['almacen'] = alm

    a = 'Clientes'; rows = drop_noise(a, read(a))
    comp = lambda g: max(g, key=lambda it: sum(1 for v in it[1].values() if v.strip()))      # criterio: registro más completo
    rows = dedupe(a, rows, kdic('Cliente', 'clientes'), pick=comp)
    cli, pref, cp, cid = [], [], [], {}
    for ln, r in rows:
        canon = c_dic(a, ln, 'Cliente', r['Cliente'], 'clientes', base=lambda v: f"{v.split(', ')[0].upper()}, {v.split(', ')[1]}")
        ap, no = canon.split(', '); c_phone(a, ln, 'Celular', r['Celular'])             # el modelo no guarda teléfono del cliente
        calle = c_text(a, ln, 'Direccion', r['Direccion']); ciudad = c_dic(a, ln, 'Distrito', r['Distrito'], 'distritos')
        u = c_dic(a, ln, 'Atendido por', r['Atendido por'], 'usuarios')
        toks = [t for t in re.split(r'\s*(?:,|/|\s-\s)\s*', r['Preferencias'].strip()) if t]
        vals = []
        for t in toks:
            v = D['preferencias'].match(t)
            if v is None: REVISION.append((a, ln, 'Preferencias', t))
            else: vals.append(v)
        if r['Preferencias'] != ', '.join(vals): log(a, ln, 'Preferencias', 'TIPOGRAFICO', r['Preferencias'], ' | '.join(vals))
        cid[canon] = len(cli) + 1; cli.append((cid[canon], no, ap, calle, ciudad, uid[u]))
        for v in vals:
            if v not in pref: pref.append(v)
            cp.append((cid[canon], pref.index(v) + 1))
    T['cliente'] = cli; T['preferencia'] = [(i + 1, p) for i, p in enumerate(pref)]; T['cliente_preferencia'] = cp

    a = 'Servicios'; rows = dedupe(a, drop_noise(a, read(a)), kdic('Servicio', 'servicios')); srv, sid, sdur = [], {}, {}
    for ln, r in rows:
        n = c_dic(a, ln, 'Servicio', r['Servicio'], 'servicios'); desc = c_text(a, ln, 'Descripcion', r['Descripcion'])
        pr = c_money(a, ln, 'Precio', r['Precio']); du = c_dur(a, ln, 'Duracion', r['Duracion'])
        sid[n] = len(srv) + 1; sdur[sid[n]] = du; srv.append((sid[n], n, desc, pr, du))
    T['servicio'] = srv

    a = 'Productos'; rows = dedupe(a, drop_noise(a, read(a)), kdic('Producto', 'productos')); prd, pid = [], {}
    for ln, r in rows:
        n = c_dic(a, ln, 'Producto', r['Producto'], 'productos'); pres = c_text(a, ln, 'Presentacion', r['Presentacion'])
        pr = c_money(a, ln, 'Precio', r['Precio']); st = c_int(a, ln, 'Stock', r['Stock']); al = c_dic(a, ln, 'Almacen', r['Almacen'], 'almacenes')
        pid[n] = len(prd) + 1; prd.append((pid[n], n, pres, pr, st, aid[al]))          # stock INICIAL; los triggers suman pedidos y restan ventas
    T['producto'] = prd

    a = 'Insumos por servicio'
    rows = dedupe(a, drop_noise(a, read(a)), lambda r: (D['servicios'].match(r['Servicio']), D['productos'].match(r['Producto']))); sp = []
    for ln, r in rows:
        s = c_dic(a, ln, 'Servicio', r['Servicio'], 'servicios'); p = c_dic(a, ln, 'Producto', r['Producto'], 'productos')
        sp.append((sid[s], pid[p], c_int(a, ln, 'Cantidad usada', r['Cantidad usada'])))
    T['servicio_producto'] = sp

    a = 'Proveedores'; rows = dedupe(a, drop_noise(a, read(a)), kdic('Razon social', 'proveedores')); prv, vid = [], {}
    for ln, r in rows:
        n = c_dic(a, ln, 'Razon social', r['Razon social'], 'proveedores'); tel = c_phone(a, ln, 'Telefono', r['Telefono'])
        cor = c_text(a, ln, 'Correo', r['Correo'], lower=True)
        vid[n] = len(prv) + 1; prv.append((vid[n], n, tel, cor))
    T['proveedor'] = prv

    a = 'Citas'; rows = drop_noise(a, read(a))
    mod = lambda r: dt.datetime.strptime(r['Modificado'], '%d/%m/%Y %H:%M')
    rows = dedupe(a, rows, lambda r: (r['N° cita'].strip(), D['servicios'].match(r['Servicio'])), pick=lambda g: max(g, key=lambda it: mod(it[1])))  # criterio: modificación más reciente
    dur = {}
    QUIET[0] = True                                     # 1.ª pasada sin registrar: duración total de cada cita
    for ln, r in rows:
        n = int(r['N° cita']); dur[n] = dur.get(n, 0) + sdur[sid[c_dic(a, ln, 'Servicio', r['Servicio'], 'servicios')]]
    QUIET[0] = False
    head, lines = {}, []
    for ln, r in rows:
        n = int(r['N° cita']); f = c_date(a, ln, 'Fecha', r['Fecha']); hi = c_time(a, ln, 'Hora inicio', r['Hora inicio'])
        hf = parse_time(r['Hora fin']) if r['Hora fin'].strip() else None
        derivada = add_min(hi, dur[n])
        if not r['Hora fin'].strip(): log(a, ln, 'Hora fin', 'NULO', '', derivada.strftime('%H:%M:%S'))
        else:
            c_time(a, ln, 'Hora fin', r['Hora fin'])
            if hf != derivada: log(a, ln, 'Hora fin', 'INCONSISTENCIA', r['Hora fin'], derivada.strftime('%H:%M:%S'))
        cl = c_dic(a, ln, 'Cliente', r['Cliente'], 'clientes', base=lambda v: f"{v.split(', ')[1]} {v.split(', ')[0]}")
        s = c_dic(a, ln, 'Servicio', r['Servicio'], 'servicios'); pr = c_money(a, ln, 'Precio cobrado', r['Precio cobrado'])
        if r['Estado'].strip(): est = c_dic(a, ln, 'Estado', r['Estado'], 'estados_cita')
        else:
            est = 'Cancelada' if re.search(r'cancel', r['Observaciones'], re.I) else None      # se recupera de Observaciones
            log(a, ln, 'Estado', 'NULO', '', est)
            if est is None: REVISION.append((a, ln, 'Estado', ''))
        u = c_dic(a, ln, 'Registrada por', r['Registrada por'], 'usuarios')
        lines.append((n, sid[s], pr))
        if n not in head or mod(r) >= head[n][0]:
            ap, no = cl.split(', ')
            head[n] = (mod(r), f, hi, derivada, f'Cliente: {no} {ap}.' + (f" {r['Observaciones'].strip()}" if r['Observaciones'].strip() else ''), est, uid[u])
    T['_cita'] = head; T['_cita_srv'] = lines

    a = 'Ventas'; rows = dedupe(a, drop_noise(a, read(a)), lambda r: (r['N° venta'].strip(), D['productos'].match(r['Producto']))); vent, det, tot_src = {}, [], {}
    for ln, r in rows:
        n = int(r['N° venta']); f = c_date(a, ln, 'Fecha', r['Fecha']); p = c_dic(a, ln, 'Producto', r['Producto'], 'productos')
        pr = c_money(a, ln, 'Precio unit.', r['Precio unit.']); tt = c_money(a, ln, 'Total venta', r['Total venta'])
        nlin = sum(1 for _, x in rows if int(x['N° venta']) == n)
        if r['Cantidad'].strip(): q = c_int(a, ln, 'Cantidad', r['Cantidad'])
        else:
            q = int(tt / pr) if nlin == 1 and tt and pr and (tt / pr) == int(tt / pr) else None   # cantidad = total ÷ precio (venta de una línea)
            log(a, ln, 'Cantidad', 'NULO', '', q)
            if q is None: REVISION.append((a, ln, 'Cantidad', ''))
        vent.setdefault(n, f); tot_src.setdefault(n, (ln, tt)); det.append((n, pid[p], q, pr))
    for n, (ln, tt) in tot_src.items():
        calc = sum(Decimal(q) * pr for m, _, q, pr in det if m == n)
        if tt != calc: log(a, ln, 'Total venta', 'INCONSISTENCIA', str(tt), calc)
    T['_venta'] = vent; T['_det_venta'] = det

    a = 'Pedidos'; rows = dedupe(a, drop_noise(a, read(a)), lambda r: (r['N° pedido'].strip(), D['productos'].match(r['Producto']))); ped, dped, fechas = {}, [], {}
    for ln, r in rows:
        if r['Fecha'].strip(): fechas.setdefault(int(r['N° pedido']), parse_date(r['Fecha']))
    for ln, r in rows:
        n = int(r['N° pedido'])
        if r['Fecha'].strip(): f = c_date(a, ln, 'Fecha', r['Fecha'])
        else: f = fechas[n]; log(a, ln, 'Fecha', 'NULO', '', f.isoformat())                   # fecha tomada de otra línea del mismo pedido
        pv = c_dic(a, ln, 'Proveedor', r['Proveedor'], 'proveedores'); p = c_dic(a, ln, 'Producto', r['Producto'], 'productos')
        q = c_int(a, ln, 'Cantidad', r['Cantidad']); pr = c_money(a, ln, 'Precio unit.', r['Precio unit.']); u = c_dic(a, ln, 'Registrado por', r['Registrado por'], 'usuarios')
        ped.setdefault(n, (f, uid[u], vid[pv])); dped.append((n, pid[p], q, pr))
    T['_pedido'] = ped; T['_det_pedido'] = dped

def fmt(v):
    if v is None: return ''
    if isinstance(v, dt.time): return v.strftime('%H:%M:%S')
    if isinstance(v, dt.date): return v.isoformat()
    if isinstance(v, Decimal): return f'{v:.2f}'
    return str(v)

def armar_tablas_finales():
    est = D['estados_cita'].valid; est_id = {v: i + 1 for i, v in enumerate(est)}
    T['estado_cita'] = [(i + 1, v) for i, v in enumerate(est)]
    T['cita'] = [(n, h[1], h[2], h[3], h[4], est_id[h[5]], h[6]) for n, h in sorted(T['_cita'].items())]
    T['pedido_compra'] = [(n, f, u, p) for n, (f, u, p) in sorted(T['_pedido'].items())]
    T['detalle_pedido'] = sorted(T['_det_pedido'], key=lambda x: (x[0], x[1]))
    T['detalle_venta'] = sorted(T['_det_venta'], key=lambda x: (x[0], x[1]))
    tot = {n: sum(Decimal(q) * pr for m, _, q, pr in T['detalle_venta'] if m == n) for n in T['_venta']}       # total = suma del detalle
    T['venta'] = [(n, f, tot[n]) for n, f in sorted(T['_venta'].items())]
    T['cita_servicio'] = sorted(T['_cita_srv'], key=lambda x: (x[0], x[1]))
    T['_stock_inicial'] = {p[0]: p[4] for p in T['producto']}
    T['producto'] = [(p[0], p[1], p[2], p[3],                                                                  # stock final = inicial + pedidos − ventas
                      p[4] + sum(d[2] for d in T['detalle_pedido'] if d[1] == p[0]) - sum(d[2] for d in T['detalle_venta'] if d[1] == p[0]), p[5]) for p in T['producto']]

ORDEN = ['usuario', 'especialidad', 'preferencia', 'estado_cita', 'proveedor', 'servicio', 'almacen', 'empleado', 'cliente', 'cliente_preferencia',
         'producto', 'cita', 'cita_servicio', 'servicio_producto', 'pedido_compra', 'detalle_pedido', 'venta', 'detalle_venta']
COLS = {'usuario': 'id_usuario,nombre,telefono', 'especialidad': 'id_especialidad,nombre_especialidad', 'preferencia': 'id_preferencia,descripcion',
        'estado_cita': 'id_estado,descripcion', 'proveedor': 'codigo_proveedor,razon_social,telefono,correo', 'servicio': 'codigo_servicio,nombre,descripcion,precio,duracion',
        'almacen': 'codigo_almacen,id_usuario', 'empleado': 'codigo_empleado,id_especialidad,id_usuario', 'cliente': 'codigo_cliente,nombres,apellidos,calle,ciudad,id_usuario',
        'cliente_preferencia': 'codigo_cliente,id_preferencia', 'producto': 'codigo_producto,nombre,descripcion,precio_unitario,stock,codigo_almacen',
        'cita': 'numero_registro,fecha,hora_inicio,hora_fin,observaciones,id_estado,id_usuario', 'cita_servicio': 'numero_registro,codigo_servicio,precio',
        'servicio_producto': 'codigo_servicio,codigo_producto,cantidad_usada', 'pedido_compra': 'id_pedido,fecha,id_usuario,codigo_proveedor',
        'detalle_pedido': 'id_pedido,codigo_producto,cantidad,precio', 'venta': 'numero_venta,fecha,total', 'detalle_venta': 'numero_venta,codigo_producto,cantidad,precio'}
INSERT = {t: f"INSERT INTO {t} ({c}) VALUES ({','.join(['%s'] * len(c.split(',')))})" for t, c in COLS.items()}
GRAVES = {1146, 1054, 1064, 2006, 2013, 1049}        # errores que no son de una fila: se detiene la carga

def escribir_limpios():
    for t in ORDEN:
        with open(os.path.join(OUT, t + '.csv'), 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f); w.writerow(COLS[t].split(','))
            for r in T[t]: w.writerow([fmt(v) for v in r])

def sql_statements(path):
    delim, buf, out = ';', [], []
    for line in open(path, encoding='utf-8'):
        s = line.strip()
        if s.upper().startswith('DELIMITER '): delim = s.split()[1]; continue
        if not s or s.startswith('--'): continue
        buf.append(line)
        if s.endswith(delim): out.append(''.join(buf).rstrip()[:-len(delim)]); buf = []
    return out
def esp_rows(t):
    with open(os.path.join(ESP, t + '.csv'), encoding='utf-8-sig', newline='') as f:
        rd = csv.reader(f, delimiter=';'); next(rd); return [tuple(r) for r in rd]
def ordenar(rows):
    return sorted(rows, key=lambda r: tuple((0, int(x)) if x.isdigit() else (1, x) for x in r[:2]))
def db_rows(cur, t):
    cur.execute(f'SELECT {COLS[t]} FROM {t}'); out = []
    for r in cur.fetchall():
        o = []
        for v in r:
            if isinstance(v, dt.timedelta): s = int(v.total_seconds()); v = f'{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}'
            o.append(v if isinstance(v, str) else fmt(v))
        out.append(tuple(o))
    return out

# ================================================================== PROGRAMA
def main():
    t0 = time.time(); demo = '--demo-cuarentena' in sys.argv
    say('=== ETL Salón Spa Rodríguez (origen: libros Excel) ===\n')
    extraer()
    say('\nTRANSFORMACIÓN · Limpieza de los CSV extraídos (sin tocar la base de datos)')
    transformar(); armar_tablas_finales()
    if demo:
        T['detalle_venta'].append((1, 9, 1, Decimal('0.00')))                                       # viola CHECK (precio > 0)
        T['cita'].append((99, dt.date(2026, 10, 30), dt.time(10, 0), None, 'Cliente: prueba de cuarentena.', 1, 999))   # viola FK (usuario 999)
        say('  [DEMO] se agregaron 2 filas inválidas para probar la cuarentena')
    escribir_limpios()
    for n, s in STAT.items(): say(f'  {n:22s} leídas={s["leidas"]:3d}  vacías={s["vacias"]}  resumen={s["resumen"]}  duplicados={s["duplicados"]}  útiles={s["utiles"]}')
    tipos = Counter(c[3] for c in CORR); say('  correcciones por operación: ' + ', '.join(f'{k}={v}' for k, v in sorted(tipos.items())))
    chk('TRF', 'Ningún valor quedó sin reconocer (revisión manual = 0)', not REVISION, f'{len(REVISION)} valores' if REVISION else '')
    if not demo:
        for t in ORDEN:
            exp = esp_rows(t); got = [tuple(fmt(v) for v in r) for r in T[t]]
            chk('TRF', f'CSV limpio {t}: {len(got)} filas, igual a lo esperado', ordenar(got) == ordenar(exp), critica=True)

    # ---------------- FASE 1
    say('\nFASE 1 · Conexión y preparación del destino')
    c = cfg(); conn = pymysql.connect(host=c['host'], port=c['port'], user=c['user'], password=c['password'], charset='utf8mb4', autocommit=False)
    cur = conn.cursor(); cur.execute('SELECT VERSION()'); ver = cur.fetchone()[0]
    chk('F1', f'Conexión exitosa a {c["host"]}:{c["port"]}', True)
    vt = tuple(int(x) for x in re.match(r'(\d+)\.(\d+)\.(\d+)', ver).groups())
    ok = vt >= (10, 2, 1) if 'mariadb' in ver.lower() else vt >= (8, 0, 16)
    chk('F1', f'Versión {ver} aplica los CHECK (MySQL ≥ 8.0.16 / MariaDB ≥ 10.2.1)', ok)
    if not ok: return finish(conn, t0, 1)
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE' AND table_name NOT IN ('credencial','bitacora')", (DBNAME,)); nt = cur.fetchone()[0]
    stmts = sql_statements(os.path.join(BASE, 'sql', 'spa_rodriguez.sql'))
    if nt != 18:
        for s in stmts: cur.execute(s)
        conn.commit(); say('  Estructura creada con sql/spa_rodriguez.sql (la base no existía o estaba incompleta)')
    cur.execute(f'USE {DBNAME}')
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE' AND table_name NOT IN ('credencial','bitacora')", (DBNAME,)); nt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM information_schema.referential_constraints WHERE constraint_schema=%s AND table_name NOT IN ('credencial','bitacora')", (DBNAME,)); nf = cur.fetchone()[0]
    chk('F1', 'Existen las 18 tablas del modelo físico', nt == 18, f'tablas={nt}'); chk('F1', 'Existen las 19 llaves foráneas', nf == 19, f'fks={nf}')
    trig_ddl = [s for s in stmts if s.startswith('CREATE TRIGGER')]
    for n in ('trg_detalle_venta_descuenta_stock', 'trg_detalle_pedido_aumenta_stock'): cur.execute(f'DROP TRIGGER IF EXISTS {n}')
    cur.execute('SET FOREIGN_KEY_CHECKS=0')
    for t in reversed(ORDEN): cur.execute(f'TRUNCATE TABLE {t}')
    cur.execute('SET FOREIGN_KEY_CHECKS=1'); conn.commit()
    cur.execute("SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=%s", (DBNAME,)); ntr = cur.fetchone()[0]
    tot0 = sum((cur.execute(f'SELECT COUNT(*) FROM {t}'), cur.fetchone()[0])[1] for t in ORDEN)
    chk('F1', 'Destino preparado: triggers de stock retirados y tablas vacías (la estructura se conserva)', ntr == 0 and tot0 == 0, f'triggers={ntr}, filas={tot0}')

    # ---------------- FASE 2
    say('\nFASE 2 · Validar los CSV transformados (ya limpios)')
    cur.execute("SELECT table_name, column_name, is_nullable, data_type, character_maximum_length, extra FROM information_schema.columns WHERE table_schema=%s ORDER BY ordinal_position", (DBNAME,))
    meta = {}
    for tn, cn, nl, dtp, ml, ex in cur.fetchall(): meta.setdefault(tn, {})[cn] = (nl == 'YES', dtp, ml)
    cur.execute("SELECT table_name, column_name FROM information_schema.key_column_usage WHERE table_schema=%s AND constraint_name='PRIMARY' ORDER BY ordinal_position", (DBNAME,))
    pks = {}
    for tn, cn in cur.fetchall(): pks.setdefault(tn, []).append(cn)
    PAT = {'int': r'-?\d+', 'decimal': r'-?\d+\.\d{2}', 'date': r'\d{4}-\d{2}-\d{2}', 'time': r'\d{2}:\d{2}:\d{2}'}
    problemas = []
    for t in ORDEN:
        path = os.path.join(OUT, t + '.csv')
        try: rows = list(csv.reader(open(path, encoding='utf-8-sig', newline='')))
        except (OSError, UnicodeDecodeError) as e: problemas.append((t, 0, f'archivo ilegible: {e}')); continue
        if rows[0] != COLS[t].split(','): problemas.append((t, 1, f'encabezados {rows[0]} ≠ columnas de la tabla')); continue
        seen = set()
        for i, r in enumerate(rows[1:], 2):
            for h, v in zip(rows[0], r):
                nullable, dtp, ml = meta[t][h]
                if v == '':
                    if not nullable: problemas.append((t, i, f'valor obligatorio vacío en {h}'))
                elif dtp in PAT and not re.fullmatch(PAT[dtp], v): problemas.append((t, i, f'{h}="{v}" no es {dtp}'))
                elif dtp in ('varchar', 'text') and ml and len(v) > ml: problemas.append((t, i, f'{h} excede {ml} caracteres'))
            k = tuple(r[rows[0].index(p)] for p in pks[t])
            if k in seen: problemas.append((t, i, f'clave primaria repetida {k}'))
            seen.add(k)
        say(f'  {t:20s} {len(rows) - 1:3d} filas · encabezados, tipos, obligatorios y claves OK' if not [p for p in problemas if p[0] == t] else f'  {t:20s} CON PROBLEMAS')
    chk('F2', f'Los {len(ORDEN)} CSV existen, son legibles (UTF-8), con encabezados iguales a las columnas, tipos válidos, obligatorios completos y sin claves repetidas', not problemas,
        '; '.join(f'{p[0]} fila {p[1]}: {p[2]}' for p in problemas[:3]))
    if problemas: say('  No se carga nada.'); return finish(conn, t0, 1)

    # ---------------- FASE 3
    say('\nFASE 3 · Cargar los CSV en MySQL (orden de llaves foráneas; las filas que violan una restricción van a cuarentena)')
    cuar, leidas, insertadas = [], Counter(), Counter()
    for t in ORDEN:
        rows = list(csv.reader(open(os.path.join(OUT, t + '.csv'), encoding='utf-8-sig', newline='')))[1:]
        data = [tuple(None if v == '' else v for v in r) for r in rows]; leidas[t] = len(data); t1 = time.time()
        cur.execute('SAVEPOINT lote')
        try: cur.executemany(INSERT[t], data); insertadas[t] = len(data)
        except pymysql.MySQLError as e:
            if e.args[0] in GRAVES: conn.rollback(); say(f'  ERROR GRAVE en {t}: {e}'); chk('F3', f'Carga de {t}', False, str(e)); return finish(conn, t0, 1)
            cur.execute('ROLLBACK TO SAVEPOINT lote')
            for i, row in enumerate(data, 2):
                cur.execute('SAVEPOINT fila')
                try: cur.execute(INSERT[t], row); insertadas[t] += 1
                except pymysql.MySQLError as e2:
                    if e2.args[0] in GRAVES: conn.rollback(); say(f'  ERROR GRAVE en {t}: {e2}'); chk('F3', f'Carga de {t}', False, str(e2)); return finish(conn, t0, 1)
                    cur.execute('ROLLBACK TO SAVEPOINT fila'); cuar.append((t, i, f'error {e2.args[0]}: {e2.args[1]}', ';'.join('' if v is None else str(v) for v in row)))
        say(f'  {t:20s} leídas={leidas[t]:3d}  insertadas={insertadas[t]:3d}  rechazadas={leidas[t] - insertadas[t]}  ({(time.time() - t1) * 1000:.0f} ms)')
    conn.commit()
    with open(os.path.join(BASE, 'cuarentena.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(['tabla', 'fila_csv', 'motivo', 'datos']); w.writerows(cuar)
    for s in trig_ddl: cur.execute(s)
    conn.commit()
    say(f'  COMMIT · cuarentena.csv: {len(cuar)} fila(s) rechazada(s) · triggers de stock creados de nuevo')
    for r in cuar: say(f'    CUARENTENA {r[0]} fila {r[1]}: {r[2][:90]}')
    if demo: chk('F3', 'Cuarentena: las 2 filas inválidas fueron rechazadas con su motivo', len(cuar) == 2, f'{len(cuar)} rechazadas')
    else: chk('F3', 'Carga completa sin filas rechazadas', len(cuar) == 0, f'{len(cuar)} rechazadas')

    # ---------------- FASE 4
    say('\nFASE 4 · Verificar la migración')
    q = lambda s: (cur.execute(s), cur.fetchall())[1]
    rech = Counter(r[0] for r in cuar); total_l = total_i = total_r = 0
    for t in ORDEN:
        cur.execute(f'SELECT COUNT(*) FROM {t}'); n = cur.fetchone()[0]; total_l += leidas[t]; total_i += n; total_r += rech[t]
        chk('F4', f'{t}: filas leídas ({leidas[t]}) = insertadas ({n}) + rechazadas ({rech[t]})', leidas[t] == n + rech[t])
    chk('F4', f'Total: {total_l} leídas = {total_i} insertadas + {total_r} rechazadas', total_l == total_i + total_r)
    for t in ORDEN:
        got, exp = ordenar(db_rows(cur, t)), ordenar(esp_rows(t))
        chk('F4', f'{t}: contenido idéntico al esperado', got == exp, '' if got == exp else f'primera diferencia: {next(((g, e) for g, e in zip(got, exp) if g != e), (len(got), len(exp)))}')
    cur.execute("SELECT table_name, column_name, referenced_table_name, referenced_column_name FROM information_schema.key_column_usage WHERE table_schema=%s AND referenced_table_name IS NOT NULL", (DBNAME,))
    huer = sum(q(f'SELECT COUNT(*) FROM {a} c LEFT JOIN {p} r ON c.{b} = r.{d} WHERE c.{b} IS NOT NULL AND r.{d} IS NULL')[0][0] for a, b, p, d in cur.fetchall()) if False else 0
    fks = q(f"SELECT table_name, column_name, referenced_table_name, referenced_column_name FROM information_schema.key_column_usage WHERE table_schema='{DBNAME}' AND referenced_table_name IS NOT NULL")
    huer = sum(q(f'SELECT COUNT(*) FROM {a} c LEFT JOIN {p} r ON c.{b} = r.{d} WHERE c.{b} IS NOT NULL AND r.{d} IS NULL')[0][0] for a, b, p, d in fks)
    chk('F4', f'Filas huérfanas = 0 en las {len(fks)} llaves foráneas', huer == 0, f'{huer}')
    dif = q("SELECT COUNT(*) FROM venta v WHERE v.total <> (SELECT SUM(cantidad*precio) FROM detalle_venta d WHERE d.numero_venta=v.numero_venta)")[0][0]
    chk('F4', 'venta.total = suma de cantidad × precio de su detalle', dif == 0, f'{dif} descuadres')
    dif = q("""SELECT COUNT(*) FROM cita c WHERE c.hora_fin <> ADDTIME(c.hora_inicio, SEC_TO_TIME(60*(SELECT SUM(s.duracion) FROM cita_servicio cs
               JOIN servicio s ON s.codigo_servicio=cs.codigo_servicio WHERE cs.numero_registro=c.numero_registro)))""")[0][0]
    chk('F4', 'cita.hora_fin = hora_inicio + duración de sus servicios', dif == 0, f'{dif} descuadres')
    ini = T['_stock_inicial']; dif = 0
    for cod, st in q('SELECT codigo_producto, stock FROM producto'):
        ent = q(f'SELECT COALESCE(SUM(cantidad),0) FROM detalle_pedido WHERE codigo_producto={cod}')[0][0]; sal = q(f'SELECT COALESCE(SUM(cantidad),0) FROM detalle_venta WHERE codigo_producto={cod}')[0][0]
        dif += st != ini[cod] + ent - sal
    chk('F4', 'Stock final por producto = stock inicial + pedidos − ventas', dif == 0, f'{dif} descuadres')
    cur.execute("SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=%s", (DBNAME,)); chk('F4', 'Triggers de stock activos de nuevo', cur.fetchone()[0] == 2)

    # ---------------- FASE 5
    say('\nFASE 5 · Pruebas de reglas de negocio')
    say('  Citas por estado:'); [say(f'    {e:11s} {n}') for e, n in q("SELECT e.descripcion, COUNT(*) FROM cita c JOIN estado_cita e ON e.id_estado=c.id_estado GROUP BY e.descripcion ORDER BY 2 DESC, 1")]
    ing = q("SELECT COALESCE(SUM(cs.precio),0) FROM cita_servicio cs JOIN cita c ON c.numero_registro=cs.numero_registro JOIN estado_cita e ON e.id_estado=c.id_estado WHERE e.descripcion='Atendida'")[0][0]
    vtot = q('SELECT SUM(total) FROM venta')[0][0]
    say(f'  Ingresos por servicios atendidos: S/ {ing}   |   Ventas de productos: S/ {vtot}')
    chk('F5', 'Ingresos y ventas coinciden con lo esperado (S/ 410.00 y S/ 420.00)', ing == Decimal('410.00') and vtot == Decimal('420.00'), f'servicios={ing}, ventas={vtot}')
    say('  Productos con stock bajo (< 30):'); [say(f'    {n:34s} {s}') for n, s in q('SELECT nombre, stock FROM producto WHERE stock < 30 ORDER BY stock')]
    say('  Pruebas negativas (cada rechazo es el resultado ESPERADO; todo se revierte con ROLLBACK):')
    def neg(nombre, sql, esperado):
        try: cur.execute(sql); r = (False, 'la base NO lo rechazó')
        except pymysql.MySQLError as e:
            ok = (e.args[0] in (3819, 4025)) if esperado == 'check' else esperado.lower() in str(e).lower(); r = (ok, f'rechazado con error {e.args[0]} (esperado)')
        conn.rollback(); chk('F5', nombre, r[0], r[1])
    neg('CHECK: precio de detalle_venta ≤ 0', 'INSERT INTO detalle_venta VALUES (1,2,1,0)', 'check')
    neg('CHECK: cantidad ≤ 0 en detalle_pedido', 'INSERT INTO detalle_pedido VALUES (1,2,0,5)', 'check')
    neg('CHECK: teléfono de 9 dígitos', "INSERT INTO usuario (nombre,telefono) VALUES ('X','12345')", 'check')
    neg('FK: cita con usuario inexistente', "INSERT INTO cita (fecha,hora_inicio,id_estado,id_usuario) VALUES ('2026-10-20','10:00',1,999)", 'foreign key')
    neg('UNIQUE: estado de cita repetido', "INSERT INTO estado_cita (descripcion) VALUES ('Atendida')", 'duplicate')
    neg('Trigger: venta mayor al stock disponible', 'INSERT INTO detalle_venta VALUES (1,3,9999,42.5)', 'stock insuficiente')
    cur.execute('SELECT COUNT(*) FROM cliente_preferencia'); a0 = cur.fetchone()[0]
    cur.execute('DELETE FROM cliente WHERE codigo_cliente=1'); cur.execute('SELECT COUNT(*) FROM cliente_preferencia'); a1 = cur.fetchone()[0]; conn.rollback()
    chk('F5', 'CASCADE: al borrar un cliente se borran sus preferencias', a1 < a0, f'{a0} → {a1} (revertido)')
    cur.execute('SELECT COUNT(*) FROM cliente'); chk('F5', 'ROLLBACK dejó los datos intactos', cur.fetchone()[0] == len(T['cliente']))

    # ---------------- detección
    say('\nDETECCIÓN · errores sembrados en los Excel vs. corregidos por el ETL')
    sem = list(csv.DictReader(open(os.path.join(BASE, 'bitacora_errores_sembrados.csv'), encoding='utf-8-sig'), delimiter=';'))
    det = {(a, str(l), c_, t) for a, l, c_, t, *_ in CORR}; por = {}
    for s in sem:
        t = s['tipo_error']; por.setdefault(t, [0, 0])
        if s['columna'] == '(fila completa)': continue
        por[t][0] += 1; por[t][1] += (s['hoja'], s['fila_excel'], s['columna'], t) in det
    for t, (n, d) in sorted(por.items()):
        if n: say(f'  {t:15s} sembrados={n:3d}  detectados={d:3d}'); chk('DET', f'{t}: se detectaron los {n} errores sembrados', d == n, f'{d}/{n}', critica=False)
    rowdup = sum(v['duplicados'] for v in STAT.values()); rowvac = sum(v['vacias'] + v['resumen'] for v in STAT.values())
    sd = sum(1 for s in sem if s['tipo_error'] == 'DUPLICADO'); sv = sum(1 for s in sem if s['columna'] == '(fila completa)' and s['tipo_error'] == 'NULO')
    chk('DET', 'Duplicados eliminados = sembrados', rowdup == sd, f'{rowdup}/{sd}'); chk('DET', 'Filas vacías y de resumen eliminadas = sembradas', rowvac == sv, f'{rowvac}/{sv}')

    # ---------------- FASE 6
    say('\nFASE 6 · Reporte y evidencias')
    return finish(conn, t0, 0)

def finish(conn, t0, code):
    crit = [r for r in RES if r[2] == 'FAIL']
    say(f'  Reporte: reporte_etl.md · log_etl.txt · cuarentena.csv · csv_extraidos/ · csv_limpios/')
    say(f'\nRESULTADO: {sum(r[2] == "PASS" for r in RES)} PASS · {len(crit)} FAIL · {sum(r[2] == "AVISO" for r in RES)} AVISO  ({time.time() - t0:.1f} s)')
    with open(os.path.join(BASE, 'reporte_etl.md'), 'w', encoding='utf-8') as f:
        f.write('# Reporte del ETL — Salón Spa Rodríguez\n\n| Fase | Prueba | Resultado | Detalle |\n|---|---|---|---|\n')
        for r in RES: f.write(f'| {r[0]} | {r[1]} | **{r[2]}** | {r[3]} |\n')
        f.write('\n## Correcciones aplicadas (primeras 60)\n\n| Hoja | Fila Excel | Columna | Tipo | Valor sucio | Valor limpio |\n|---|---|---|---|---|---|\n')
        for c in CORR[:60]: f.write('| ' + ' | '.join(str(x).replace('|', '/') for x in c) + ' |\n')
    with open(os.path.join(BASE, 'log_etl.txt'), 'w', encoding='utf-8') as f: f.write('\n'.join(LOGL))
    try: conn.close()
    except Exception: pass
    return 1 if crit or code else 0

if __name__ == '__main__':
    sys.exit(main())
