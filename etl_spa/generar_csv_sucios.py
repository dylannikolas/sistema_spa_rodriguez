# -*- coding: utf-8 -*-
"""
Genera los CSV "sucios" (fuente) del Salón Spa Rodríguez, los CSV "esperados"
(resultado correcto tras el ETL, una tabla del modelo físico de 18 tablas),
los diccionarios de valores válidos y la bitácora de errores sembrados.
DATOS SIMULADOS: el caso no entrega datos reales del negocio.
"""
import csv, os, datetime as dt, unicodedata, difflib, sys

BASE = os.path.dirname(os.path.abspath(__file__))
for d in ('excel_sucios', 'esperado', 'diccionarios'):
    os.makedirs(os.path.join(BASE, d), exist_ok=True)

def pe(s):                 # '2026-10-05' -> '05/10/2026'
    y, m, d = s.split('-'); return f'{d}/{m}/{y}'
def money(x): return f'{x:.2f}'

# ----------------------------------------------------------------- verdad
USU = {1: ('Rosa Rodríguez Salazar', '987654321'), 2: ('Lucía Paredes Huamán', '986543210'),
       3: ('Carmen Soto Villanueva', '985432109'), 4: ('Marco Quispe Ramos', '984321098'),
       5: ('Andrea Vargas Delgado', None), 6: ('Jorge Mendoza Cáceres', '982109876')}
USU_FUNCION = {1: 'Recepción y administración', 2: 'Terapeuta', 3: 'Terapeuta', 4: 'Terapeuta', 5: 'Terapeuta', 6: 'Almacén'}
EMPLEADOS = [(2, 'Masajista terapéutica'), (3, 'Esteticista facial'), (4, 'Masajista deportivo'), (5, 'Manicura y pedicura')]
ALMACENES = [('Principal', 6), ('Recepción', 1)]
CLIENTES = [  # id, apellidos, nombres, calle, ciudad, usuario, preferencias, celular
    (1, 'Fernández Luna', 'María', 'Av. Larco 345', 'Miraflores', 1, ['Masajes relajantes', 'Aromas de lavanda'], '999111222'),
    (2, 'Gómez Rojas', 'Patricia', 'Calle Los Pinos 128', 'San Isidro', 2, ['Limpieza facial'], '999222333'),
    (3, 'Ramírez Torres', 'Sofía', 'Av. Primavera 1520', 'Santiago de Surco', 3, ['Manicura en gel', 'Citas por la tarde'], '999333444'),
    (4, 'Castillo Meza', 'Valeria', 'Jr. Cusco 410', 'Jesús María', 1, ['Aromaterapia'], '999444555'),
    (5, 'Ochoa Prado', 'Daniela', 'Av. Javier Prado Este 2890', 'San Borja', 5, ['Masaje descontracturante'], '999555666'),
    (6, 'Salas Vega', 'Camila', 'Calle Domeyer 215', 'Barranco', 2, ['Pedicura', 'Productos hipoalergénicos'], '999666777'),
    (7, 'Chávez', 'Luis Alberto', 'Av. La Molina 1105', 'La Molina', 3, ['Masaje descontracturante'], '999777888'),
    (8, 'Núñez Ponce', 'Gabriela', 'Av. Arequipa 2230', 'Lince', 5, ['Exfoliación corporal', 'Citas por la mañana'], '999888999')]
SERVICIOS = [(1, 'Masaje relajante', 'Masaje corporal con aceites esenciales', 90.0, 60),
             (2, 'Masaje descontracturante', 'Masaje terapéutico de tejido profundo', 110.0, 60),
             (3, 'Limpieza facial profunda', 'Limpieza, exfoliación y mascarilla', 120.0, 75),
             (4, 'Manicura en gel', 'Manicura con esmalte en gel', 40.0, 45),
             (5, 'Pedicura spa', 'Pedicura con exfoliación e hidratación', 55.0, 60),
             (6, 'Exfoliación corporal', 'Exfoliación con café y envoltura hidratante', 100.0, 50),
             (7, 'Depilación con cera', 'Depilación de zonas a elección', 60.0, 30),
             (8, 'Aromaterapia', None, 70.0, 40)]          # descripción no disponible en la fuente
PRODUCTOS = [(1, 'Aceite esencial de lavanda', 'Frasco de 30 ml', 35.0, 25, 'Principal'),
             (2, 'Aceite de almendras para masaje', 'Botella de 500 ml', 48.0, 18, 'Principal'),
             (3, 'Crema hidratante facial', 'Pote de 50 g', 42.5, 30, 'Principal'),
             (4, 'Mascarilla de arcilla verde', 'Pote de 200 g', 38.0, 22, 'Principal'),
             (5, 'Esmalte en gel', 'Frasco de 15 ml, colores surtidos', 18.0, 60, 'Recepción'),
             (6, 'Removedor de esmalte', 'Botella de 250 ml', 9.5, 40, 'Recepción'),
             (7, 'Sales de baño aromáticas', 'Bolsa de 500 g', 25.0, 35, 'Principal'),
             (8, 'Exfoliante corporal de café', 'Pote de 300 g', 45.0, 20, 'Principal'),
             (9, 'Cera depilatoria tibia', 'Pote de 400 g', 32.0, 15, 'Principal'),
             (10, 'Toallas descartables', None, 28.0, 50, 'Recepción')]   # presentación no disponible
INSUMOS = [(1, 2, 1), (1, 1, 1), (1, 10, 1), (2, 2, 1), (2, 10, 1), (3, 3, 1), (3, 4, 1), (3, 10, 2), (4, 5, 1), (4, 6, 1),
           (5, 5, 1), (5, 6, 1), (5, 7, 1), (6, 8, 1), (6, 3, 1), (7, 9, 1), (7, 10, 1), (8, 1, 1), (8, 7, 1)]
PROVEEDORES = [(1, 'Distribuidora Cosmética Andina S.A.C.', '987100100', 'ventas@cosmeticaandina.pe'),
               (2, 'Aromas del Perú E.I.R.L.', '987200200', 'contacto@aromasdelperu.pe'),
               (3, 'Insumos Spa Lima S.A.C.', '987300300', None),
               (4, 'Belleza Total Perú S.A.', '987400400', 'comercial@bellezatotal.pe')]
ESTADOS = ['Pendiente', 'Confirmada', 'Atendida', 'Cancelada']
CITAS = [  # nro, fecha, ini, fin, cliente, [(servicio, precio)], estado, usuario, obs
    (1, '2026-10-05', '09:00', '10:00', 1, [(1, 90.0)], 'Atendida', 2, 'Prefiere aroma de lavanda.'),
    (2, '2026-10-05', '11:00', '12:15', 2, [(3, 120.0)], 'Atendida', 3, ''),
    (3, '2026-10-06', '15:00', '16:45', 3, [(4, 40.0), (5, 55.0)], 'Atendida', 5, 'Manicura y pedicura el mismo día.'),
    (4, '2026-10-07', '10:00', '11:00', 7, [(2, 105.0)], 'Atendida', 4, 'Molestia en la espalda alta.'),
    (5, '2026-10-08', '16:00', '16:50', 8, [(6, 100.0)], 'Cancelada', 1, 'Canceló con un día de anticipación.'),
    (6, '2026-10-10', '10:00', '11:40', 4, [(1, 90.0), (8, 70.0)], 'Confirmada', 2, 'Masaje seguido de aromaterapia.'),
    (7, '2026-10-10', '14:00', '14:30', 6, [(7, 60.0)], 'Confirmada', 1, 'Piel sensible, usar cera hipoalergénica.'),
    (8, '2026-10-12', '09:30', '10:45', 2, [(3, 120.0)], 'Pendiente', 3, ''),
    (9, '2026-10-13', '17:00', '18:00', 6, [(5, 55.0)], 'Pendiente', 5, ''),
    (10, '2026-10-14', '11:00', '12:00', 5, [(2, 110.0)], 'Pendiente', 4, '')]
PEDIDOS = [(1, '2026-09-15', 6, 2, [(1, 20, 24.0), (7, 30, 17.5)]),
           (2, '2026-09-22', 6, 1, [(3, 25, 29.0), (4, 20, 26.0), (2, 15, 34.0)]),
           (3, '2026-10-01', 1, 3, [(10, 40, 19.0), (6, 30, 6.5), (5, 50, 12.0)]),
           (4, '2026-10-06', 6, 4, [(9, 12, 22.0), (8, 15, 31.5)])]
VENTAS = [(1, '2026-10-03', [(1, 2, 35.0), (7, 1, 25.0)]), (2, '2026-10-04', [(3, 1, 42.5)]),
          (3, '2026-10-05', [(8, 1, 45.0), (4, 1, 38.0)]), (4, '2026-10-06', [(5, 3, 18.0), (6, 1, 9.5)]),
          (5, '2026-10-07', [(2, 1, 48.0), (10, 2, 28.0)]), (6, '2026-10-08', [(9, 1, 32.0)])]

def full(c): return f'{c[2]} {c[1]}'                  # nombres apellidos
SVC = {s[0]: s for s in SERVICIOS}; PRD = {p[0]: p for p in PRODUCTOS}; CLI = {c[0]: c for c in CLIENTES}
PROV = {p[0]: p for p in PROVEEDORES}

# ----------------------------------------------------------- infraestructura
class Row:
    def __init__(self, vals, inj=None, ref=None, tag=None):
        self.vals, self.inj, self.ref, self.tag = vals, inj or [], ref, tag
BIT = []
REGLA = {'NULO': 'Recuperar desde otra columna/fila; si es opcional queda NULL; no se imputa media/mediana',
         'DUPLICADO': 'Conservar un solo registro (más reciente, más completo o primera ocurrencia)',
         'TIPOGRAFICO': 'Normalizar (trim, mayúsculas, tildes) y validar contra diccionario/alias',
         'TIPO_DATO': 'Quitar S/, unidades, separadores y convertir al tipo de la columna',
         'FECHA_HORA': 'Interpretar con día primero (dd/mm/aaaa, 24 h hora Lima) y convertir a DATE/TIME de MySQL',
         'INCONSISTENCIA': 'Recalcular el dato derivado a partir del detalle'}

def mk(cols, clean, dirt=None):
    dirt = dirt or {}
    vals = [dirt[c][0] if c in dirt else clean[c] for c in cols]
    inj = [(c, t[1], t[0], t[2]) for c, t in dirt.items() for t in [t]]
    return Row(vals, inj)
def D(sucio, tipo, esperado): return (sucio, tipo, esperado)
def dup(row, vals=None, nota='fila repetida'):
    r = Row(list(vals or row.vals), [('(fila completa)', 'DUPLICADO', nota, 'se conserva una sola')], ref=row); return r
def blank(n): return Row([''] * n, [('(fila completa)', 'NULO', 'fila vacía', 'se elimina')])
def footer(n, text): return Row([text] + [''] * (n - 1), [('(fila completa)', 'NULO', 'fila de resumen: ' + text, 'se elimina (no es dato de negocio)')])

import re as _re
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
SRC_MAP = {'personal.csv': ('Spa_Personal_y_Clientes.xlsx', 'Personal'), 'almacenes.csv': ('Spa_Personal_y_Clientes.xlsx', 'Almacenes'),
           'clientes.csv': ('Spa_Personal_y_Clientes.xlsx', 'Clientes'), 'servicios.csv': ('Spa_Catalogo.xlsx', 'Servicios'),
           'productos.csv': ('Spa_Catalogo.xlsx', 'Productos'), 'insumos_servicio.csv': ('Spa_Catalogo.xlsx', 'Insumos por servicio'),
           'proveedores.csv': ('Spa_Catalogo.xlsx', 'Proveedores'), 'citas.csv': ('Spa_Citas.xlsx', 'Citas'),
           'ventas.csv': ('Spa_Ventas_y_Pedidos.xlsx', 'Ventas'), 'pedidos.csv': ('Spa_Ventas_y_Pedidos.xlsx', 'Pedidos')}
WBS = {}
HEADER_ROW = 4                      # filas 1-2: título; fila 3: vacía; fila 4: cabecera; datos desde la 5
DATECOLS, TIMECOLS, DTCOLS = {'Fecha'}, {'Hora inicio', 'Hora fin'}, {'Modificado'}
MONEYCOLS = {'Precio', 'Precio cobrado', 'Precio unit.', 'Total venta'}
INTCOLS = {'Stock', 'Cantidad', 'Cantidad usada', 'Duracion', 'N° cita', 'N° venta', 'N° pedido'}
def nativo(col, v):
    """Como en un Excel real: los valores limpios se guardan como fecha/hora/número; los sucios quedan como texto."""
    if v == '': return None, None
    if col in DATECOLS and _re.fullmatch(r'\d{2}/\d{2}/\d{4}', v): d, m, y = map(int, v.split('/')); return dt.date(y, m, d), 'dd/mm/yyyy'
    if col in TIMECOLS and _re.fullmatch(r'\d{2}:\d{2}', v): h, m = map(int, v.split(':')); return dt.time(h, m), 'hh:mm'
    if col in DTCOLS and _re.fullmatch(r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}', v): return dt.datetime.strptime(v, '%d/%m/%Y %H:%M'), 'dd/mm/yyyy hh:mm'
    if col in MONEYCOLS and _re.fullmatch(r'\d+\.\d{2}', v): return float(v), '"S/" #,##0.00'
    if col in INTCOLS and _re.fullmatch(r'\d+', v): return int(v), '0'
    return v, None
def write_source(name, cols, rows):
    libro, hoja = SRC_MAP[name]
    if libro not in WBS: WBS[libro] = Workbook(); WBS[libro].remove(WBS[libro].active)
    ws = WBS[libro].create_sheet(hoja)
    ws.cell(1, 1, f'Salón Spa Rodríguez — {hoja}').font = Font(bold=True, size=14)
    ws.cell(2, 1, 'Archivo de control interno · actualizado el 14/10/2026').font = Font(italic=True, color='666666')
    for j, c in enumerate(cols, 1):
        cell = ws.cell(HEADER_ROW, j, c); cell.font = Font(bold=True, color='FFFFFF'); cell.fill = PatternFill('solid', fgColor='2E5B8A')
        ws.column_dimensions[cell.column_letter].width = max(14, min(42, len(c) + 12))
    for i, r in enumerate(rows):
        for j, (c, v) in enumerate(zip(cols, r.vals), 1):
            val, fmt_ = nativo(c, v)
            if val is None: continue
            cell = ws.cell(HEADER_ROW + 1 + i, j, val)
            if fmt_: cell.number_format = fmt_
    ws.freeze_panes = ws.cell(HEADER_ROW + 1, 1)
    for i, r in enumerate(rows):
        line = i + HEADER_ROW + 1
        for (col, tipo, sucio, esp) in r.inj:
            if tipo == 'DUPLICADO' and r.ref is not None:
                sucio = f'{sucio} (duplica la fila {rows.index(r.ref) + HEADER_ROW + 1})'
            BIT.append([name, line, col, tipo, sucio, esp, REGLA[tipo]])
    return len(rows)

def write_gold(name, cols, data):
    with open(os.path.join(BASE, 'esperado', name), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';'); w.writerow(cols)
        for r in data: w.writerow(['' if v is None else v for v in r])

# ----------------------------------------------------------------- PERSONAL
C = ['Nombre', 'Celular', 'Especialidad', 'Funcion']
esp_de = {u: e for u, e in EMPLEADOS}
def pcl(u): return {'Nombre': USU[u][0], 'Celular': USU[u][1] or '', 'Especialidad': esp_de.get(u, ''), 'Funcion': USU_FUNCION[u]}
p = {u: pcl(u) for u in USU}
r_rosa = mk(C, p[1], {'Celular': D('987 654 321', 'TIPO_DATO', '987654321'), 'Especialidad': D('', 'NULO', 'NULL (solo usuario; no genera fila en EMPLEADO)')})
r_luc = mk(C, p[2], {'Nombre': D('LUCIA PAREDES HUAMAN', 'TIPOGRAFICO', 'Lucía Paredes Huamán'), 'Celular': D('986-543-210', 'TIPO_DATO', '986543210')})
r_car = mk(C, p[3], {'Nombre': D('carmen soto villanueva ', 'TIPOGRAFICO', 'Carmen Soto Villanueva'), 'Celular': D('+51 985432109', 'TIPO_DATO', '985432109'),
                     'Especialidad': D('esteticista facial', 'TIPOGRAFICO', 'Esteticista facial')})
r_mar = mk(C, p[4], {'Nombre': D('Marco Quispe  Ramos', 'TIPOGRAFICO', 'Marco Quispe Ramos')})
r_and = mk(C, p[5], {'Celular': D('', 'NULO', 'NULL (opcional; no se inventa)'), 'Especialidad': D('Manicura y Pedicura', 'TIPOGRAFICO', 'Manicura y pedicura')})
r_jor = mk(C, p[6], {'Especialidad': D('', 'NULO', 'NULL (solo usuario; no genera fila en EMPLEADO)')})
rows = [r_rosa, r_luc, r_car, r_mar, blank(4), r_and, r_jor, dup(r_luc, [USU[2][0], USU[2][1], 'Masajista terapéutica', 'Terapeuta'], 'mismo registro escrito distinto'), footer(4, 'Total personal: 6')]
n_personal = write_source('personal.csv', C, rows)

# ----------------------------------------------------------------- CLIENTES
C = ['Cliente', 'Celular', 'Direccion', 'Distrito', 'Preferencias', 'Atendido por']
def ccl(c): return {'Cliente': f'{c[1].upper()}, {c[2]}', 'Celular': c[7], 'Direccion': c[3], 'Distrito': c[4], 'Preferencias': ', '.join(c[6]), 'Atendido por': USU[c[5]][0]}
cc = {c[0]: ccl(c) for c in CLIENTES}
NOLOAD = ' (no se carga: el modelo físico no tiene cliente.telefono)'
c1 = mk(C, cc[1], {'Celular': D('999 111 222', 'TIPO_DATO', '999111222' + NOLOAD), 'Distrito': D('miraflores', 'TIPOGRAFICO', 'Miraflores'),
                   'Preferencias': D('masajes relajantes,  Aromas de lavanda ', 'TIPOGRAFICO', 'Masajes relajantes | Aromas de lavanda')})
c2 = mk(C, cc[2], {'Cliente': D('GOMEZ ROJAS, Patricia', 'TIPOGRAFICO', 'Gómez Rojas, Patricia'), 'Atendido por': D('lucia paredes huaman', 'TIPOGRAFICO', 'Lucía Paredes Huamán')})
c3 = mk(C, cc[3], {'Distrito': D('Surco', 'TIPOGRAFICO', 'Santiago de Surco'), 'Preferencias': D('Manicura en gel / Citas por la tarde', 'TIPOGRAFICO', 'Manicura en gel | Citas por la tarde')})
c4 = mk(C, cc[4], {'Direccion': D('Jr. Cusco  410 ', 'TIPOGRAFICO', 'Jr. Cusco 410')})
c5a = mk(C, cc[5], {'Distrito': D('', 'NULO', 'San Borja (se recupera del registro duplicado más completo)')})
c5b = dup(c5a, [cc[5]['Cliente'], '999-555-666', cc[5]['Direccion'], 'San Borja', cc[5]['Preferencias'], cc[5]['Atendido por']], 'registro más completo del mismo cliente')
c5b.inj = [('(fila completa)', 'DUPLICADO', 'registro completo del mismo cliente', 'se conserva el más completo')]
c5b.ref = None
c6 = mk(C, cc[6], {'Celular': D('99966677', 'TIPO_DATO', 'NULL (8 dígitos: inválido)' + NOLOAD), 'Preferencias': D('Pedicura - Productos hipoalergénicos', 'TIPOGRAFICO', 'Pedicura | Productos hipoalergénicos')})
c7 = mk(C, cc[7])
c8 = mk(C, cc[8], {'Cliente': D('NUÑEZ PONCE, GABRIELA', 'TIPOGRAFICO', 'Núñez Ponce, Gabriela'), 'Preferencias': D('Exfoliacion corporal, Citas por la mañana', 'TIPOGRAFICO', 'Exfoliación corporal | Citas por la mañana')})
rows = [c1, c2, c3, c4, blank(6), c5a, c5b, c6, c7, c8, dup(c7, None, 'copia exacta de la fila')]
n_clientes = write_source('clientes.csv', C, rows)
# el duplicado "más completo" (c5b) deja a c5a como registro incompleto a descartar
for b in BIT:
    pass

# ---------------------------------------------------------------- SERVICIOS
C = ['Servicio', 'Descripcion', 'Precio', 'Duracion']
def scl(s): return {'Servicio': s[1], 'Descripcion': s[2] or '', 'Precio': money(s[3]), 'Duracion': str(s[4])}
sc = {s[0]: scl(s) for s in SERVICIOS}
s1 = mk(C, sc[1], {'Precio': D('S/ 90.00', 'TIPO_DATO', '90.00'), 'Duracion': D('60 min', 'TIPO_DATO', '60')})
s2 = mk(C, sc[2], {'Precio': D('S/110', 'TIPO_DATO', '110.00'), 'Duracion': D('60 minutos', 'TIPO_DATO', '60')})
s3 = mk(C, sc[3], {'Precio': D('120,00', 'TIPO_DATO', '120.00'), 'Duracion': D('1 h 15 min', 'TIPO_DATO', '75')})
s4 = mk(C, sc[4], {'Precio': D('S/. 40', 'TIPO_DATO', '40.00'), 'Duracion': D("45'", 'TIPO_DATO', '45')})
s5 = mk(C, sc[5], {'Servicio': D('Pedicura Spa', 'TIPOGRAFICO', 'Pedicura spa'), 'Duracion': D('1 h', 'TIPO_DATO', '60')})
s6 = mk(C, sc[6], {'Servicio': D('EXFOLIACION CORPORAL', 'TIPOGRAFICO', 'Exfoliación corporal')})
s7 = mk(C, sc[7], {'Servicio': D('Depilacion con cera', 'TIPOGRAFICO', 'Depilación con cera'), 'Precio': D('S/ 60', 'TIPO_DATO', '60.00')})
s8 = mk(C, sc[8], {'Descripcion': D('', 'NULO', 'NULL (opcional; no se inventa)')})
rows = [s1, s2, s3, s4, s5, s6, s7, s8, dup(s5, None, 'copia exacta de la fila')]
n_serv = write_source('servicios.csv', C, rows)

# ---------------------------------------------------------------- PRODUCTOS
C = ['Producto', 'Presentacion', 'Precio', 'Stock', 'Almacen']
def pcl2(p): return {'Producto': p[1], 'Presentacion': p[2] or '', 'Precio': money(p[3]), 'Stock': str(p[4]), 'Almacen': p[5]}
pc = {p[0]: pcl2(p) for p in PRODUCTOS}
r = {}
r[1] = mk(C, pc[1], {'Producto': D('Aceite escencial de lavanda', 'TIPOGRAFICO', 'Aceite esencial de lavanda'), 'Precio': D('S/ 35.00', 'TIPO_DATO', '35.00'), 'Almacen': D('principal', 'TIPOGRAFICO', 'Principal')})
r[2] = mk(C, pc[2], {'Stock': D('18 und', 'TIPO_DATO', '18')})
r[3] = mk(C, pc[3], {'Precio': D('S/. 42,50', 'TIPO_DATO', '42.50')})
r[4] = mk(C, pc[4], {'Producto': D('Mascarilla de arcilla berde', 'TIPOGRAFICO', 'Mascarilla de arcilla verde'), 'Almacen': D('PRINCIPAL', 'TIPOGRAFICO', 'Principal')})
r[5] = mk(C, pc[5], {'Precio': D(' S/ 18', 'TIPO_DATO', '18.00'), 'Almacen': D('Recepcion', 'TIPOGRAFICO', 'Recepción')})
r[6] = mk(C, pc[6], {'Precio': D('9,50', 'TIPO_DATO', '9.50'), 'Stock': D('40 unid.', 'TIPO_DATO', '40'), 'Almacen': D('recepción', 'TIPOGRAFICO', 'Recepción')})
r[7] = mk(C, pc[7], {'Producto': D('Sales de baño aromaticas', 'TIPOGRAFICO', 'Sales de baño aromáticas')})
r[8] = mk(C, pc[8], {'Producto': D('Exfoliante corporal de cafe', 'TIPOGRAFICO', 'Exfoliante corporal de café'), 'Precio': D('S/ 45', 'TIPO_DATO', '45.00')})
r[9] = mk(C, pc[9], {'Almacen': D('Principal ', 'TIPOGRAFICO', 'Principal')})
r[10] = mk(C, pc[10], {'Presentacion': D('', 'NULO', 'NULL (opcional; no se inventa)'), 'Precio': D('S/ 28.00', 'TIPO_DATO', '28.00')})
rows = [r[i] for i in range(1, 11)] + [dup(r[5], ['ESMALTE EN GEL', 'Frasco de 15 ml, colores surtidos', '18.00', '60', 'RECEPCION'], 'mismo producto escrito distinto')]
n_prod = write_source('productos.csv', C, rows)

# ---------------------------------------------------------- INSUMOS_SERVICIO
C = ['Servicio', 'Producto', 'Cantidad usada']
ins = [mk(C, {'Servicio': SVC[s][1], 'Producto': PRD[p][1], 'Cantidad usada': str(q)}) for s, p, q in INSUMOS]
ins[0] = mk(C, {'Servicio': SVC[1][1], 'Producto': PRD[2][1], 'Cantidad usada': '1'}, {'Servicio': D('masaje relajnte', 'TIPOGRAFICO', 'Masaje relajante')})
ins[7] = mk(C, {'Servicio': SVC[3][1], 'Producto': PRD[10][1], 'Cantidad usada': '2'}, {'Cantidad usada': D('2 und', 'TIPO_DATO', '2')})
ins[8] = mk(C, {'Servicio': SVC[4][1], 'Producto': PRD[5][1], 'Cantidad usada': '1'}, {'Producto': D('esmalte en gel', 'TIPOGRAFICO', 'Esmalte en gel')})
ins[13] = mk(C, {'Servicio': SVC[6][1], 'Producto': PRD[8][1], 'Cantidad usada': '1'}, {'Producto': D('Exfoliante corporal de cafe', 'TIPOGRAFICO', 'Exfoliante corporal de café')})
ins[17] = mk(C, {'Servicio': SVC[8][1], 'Producto': PRD[1][1], 'Cantidad usada': '1'}, {'Cantidad usada': D('1.0', 'TIPO_DATO', '1')})
rows = ins + [dup(ins[10], None, 'copia exacta de la fila')]
n_ins = write_source('insumos_servicio.csv', C, rows)

# -------------------------------------------------------------- PROVEEDORES
C = ['Razon social', 'Telefono', 'Correo']
def vcl(v): return {'Razon social': v[1], 'Telefono': v[2], 'Correo': v[3] or ''}
vc = {v[0]: vcl(v) for v in PROVEEDORES}
v1 = mk(C, vc[1], {'Razon social': D('DISTRIBUIDORA COSMETICA ANDINA SAC', 'TIPOGRAFICO', 'Distribuidora Cosmética Andina S.A.C.'), 'Telefono': D('987 100 100', 'TIPO_DATO', '987100100'), 'Correo': D('VENTAS@COSMETICAANDINA.PE', 'TIPOGRAFICO', 'ventas@cosmeticaandina.pe')})
v2 = mk(C, vc[2], {'Razon social': D('Aromas del Peru EIRL', 'TIPOGRAFICO', 'Aromas del Perú E.I.R.L.'), 'Telefono': D('(987) 200200', 'TIPO_DATO', '987200200')})
v3 = mk(C, vc[3], {'Correo': D('', 'NULO', 'NULL (opcional; no se inventa)')})
v4 = mk(C, vc[4], {'Telefono': D('+51 987 400 400', 'TIPO_DATO', '987400400')})
rows = [v1, v2, v3, v4, dup(v2, ['AROMAS DEL PERU E.I.R.L.', '987200200', 'contacto@aromasdelperu.pe'], 'mismo proveedor escrito distinto')]
n_prov = write_source('proveedores.csv', C, rows)

# ---------------------------------------------------------------- ALMACENES
C = ['Almacen', 'Responsable']
a1 = mk(C, {'Almacen': 'Principal', 'Responsable': USU[6][0]})
a2 = mk(C, {'Almacen': 'Recepción', 'Responsable': USU[1][0]}, {'Responsable': D('rosa rodriguez salazar', 'TIPOGRAFICO', 'Rosa Rodríguez Salazar')})
n_alm = write_source('almacenes.csv', C, [a1, a2])

# -------------------------------------------------------------------- CITAS
C = ['N° cita', 'Fecha', 'Hora inicio', 'Hora fin', 'Cliente', 'Servicio', 'Precio cobrado', 'Estado', 'Registrada por', 'Observaciones', 'Modificado']
def mod(fecha, h='18:00'):
    d = dt.date.fromisoformat(fecha) - dt.timedelta(days=2); return f'{d.day:02d}/{d.month:02d}/{d.year} {h}'
def ccita(c, k):
    srv, pr = c[5][k]
    return {'N° cita': str(c[0]), 'Fecha': pe(c[1]), 'Hora inicio': c[2], 'Hora fin': c[3], 'Cliente': full(CLI[c[4]]), 'Servicio': SVC[srv][1],
            'Precio cobrado': money(pr), 'Estado': c[6], 'Registrada por': USU[c[7]][0], 'Observaciones': c[8], 'Modificado': mod(c[1])}
cl = {(c[0], k): ccita(c, k) for c in CITAS for k in range(len(c[5]))}
FH = 'FECHA_HORA'
q = {}
q['1'] = mk(C, cl[(1, 0)], {'Hora inicio': D('9:00 am', FH, '09:00:00'), 'Hora fin': D('10:00 am', FH, '10:00:00'), 'Cliente': D('maria fernandez luna', 'TIPOGRAFICO', 'Fernández Luna, María'),
            'Servicio': D('Masaje relajnte', 'TIPOGRAFICO', 'Masaje relajante'), 'Precio cobrado': D('S/ 90.00', 'TIPO_DATO', '90.00'), 'Estado': D('atendida', 'TIPOGRAFICO', 'Atendida'),
            'Registrada por': D('LUCIA PAREDES HUAMAN', 'TIPOGRAFICO', 'Lucía Paredes Huamán')})
q['2'] = mk(C, cl[(2, 0)], {'Fecha': D('5 de octubre de 2026', FH, '2026-10-05'), 'Hora inicio': D('11h00', FH, '11:00:00'), 'Hora fin': D('', 'NULO', '12:15:00 (hora inicio + duración del servicio: 75 min)'),
            'Precio cobrado': D('120,00', 'TIPO_DATO', '120.00'), 'Estado': D('ATENDIDA ', 'TIPOGRAFICO', 'Atendida')})
q['3a'] = mk(C, cl[(3, 0)], {'Fecha': D('06-10-2026', FH, '2026-10-06'), 'Hora inicio': D('3:00 pm', FH, '15:00:00'), 'Hora fin': D('4:45 pm', FH, '16:45:00'),
             'Precio cobrado': D('S/. 40', 'TIPO_DATO', '40.00')})
q['3b'] = mk(C, cl[(3, 1)], {'Hora fin': D('', 'NULO', '16:45:00 (se recupera de la otra línea de la misma cita)'), 'Servicio': D('Pedicura Spa', 'TIPOGRAFICO', 'Pedicura spa'),
             'Estado': D('Atendidad', 'TIPOGRAFICO', 'Atendida')})
q['4'] = mk(C, cl[(4, 0)], {'Fecha': D('07.10.2026', FH, '2026-10-07'), 'Servicio': D('Masage descontracturante', 'TIPOGRAFICO', 'Masaje descontracturante'),
            'Precio cobrado': D('S/105', 'TIPO_DATO', '105.00'), 'Registrada por': D('marco quispe ramos', 'TIPOGRAFICO', 'Marco Quispe Ramos')})
q['5'] = mk(C, cl[(5, 0)], {'Fecha': D('8/10/26', FH, '2026-10-08'), 'Hora inicio': D('4:00 p. m.', FH, '16:00:00'), 'Hora fin': D('4:50 p. m.', FH, '16:50:00'),
            'Servicio': D('Exfoliacion corporal', 'TIPOGRAFICO', 'Exfoliación corporal'), 'Estado': D('', 'NULO', 'Cancelada (se recupera de Observaciones: "Canceló…")')})
q['6a'] = mk(C, cl[(6, 0)], {'Estado': D('confirmada', 'TIPOGRAFICO', 'Confirmada')})
q['6b'] = mk(C, cl[(6, 1)], {'Servicio': D('aromaterapia', 'TIPOGRAFICO', 'Aromaterapia')})
q['7'] = mk(C, cl[(7, 0)], {'Fecha': D('10 oct 2026', FH, '2026-10-10'), 'Precio cobrado': D('S/ 60', 'TIPO_DATO', '60.00'), 'Registrada por': D('Rosa Rodriguez Salazar', 'TIPOGRAFICO', 'Rosa Rodríguez Salazar')})
old8 = dict(cl[(8, 0)]); old8.update({'Hora inicio': '9:00 am', 'Hora fin': '10:15 am', 'Modificado': '08/10/2026 17:40'})
q['8old'] = Row([old8[c] for c in C], [('(fila completa)', 'DUPLICADO', 'versión antigua de la cita 8 (hora 9:00 am)', 'se conserva la versión con Modificado más reciente (09:30–10:45)')])
q['8'] = mk(C, {**cl[(8, 0)], 'Modificado': '10/10/2026 08:15'}, {'Precio cobrado': D('S/ 120', 'TIPO_DATO', '120.00')})
q['9'] = mk(C, cl[(9, 0)], {'Hora fin': D('17:30', 'INCONSISTENCIA', '18:00:00 (hora inicio 17:00 + 60 min del servicio)'), 'Estado': D('pendiente', 'TIPOGRAFICO', 'Pendiente')})
q['10'] = mk(C, cl[(10, 0)], {'Estado': D('Pendinte', 'TIPOGRAFICO', 'Pendiente')})
rows = [q['1'], q['2'], q['3a'], q['3b'], q['4'], dup(q['4'], None, 'copia exacta de la fila'), blank(11), q['5'], q['6a'], q['6b'], q['7'], q['8old'], q['8'], q['9'], q['10'],
        footer(11, 'Total de citas registradas: 10')]
n_citas = write_source('citas.csv', C, rows)

# ------------------------------------------------------------------- VENTAS
C = ['N° venta', 'Fecha', 'Producto', 'Cantidad', 'Precio unit.', 'Total venta']
def tot(v): return sum(c * p for _, c, p in v[2])
def cv(v, k):
    pr, c, p = v[2][k]
    return {'N° venta': str(v[0]), 'Fecha': pe(v[1]), 'Producto': PRD[pr][1], 'Cantidad': str(c), 'Precio unit.': money(p), 'Total venta': money(tot(v))}
vl = {(v[0], k): cv(v, k) for v in VENTAS for k in range(len(v[2]))}
w = {}
w['1a'] = mk(C, vl[(1, 0)], {'Precio unit.': D('S/ 35.00', 'TIPO_DATO', '35.00'), 'Total venta': D('S/ 95.00', 'TIPO_DATO', '95.00')})
w['1b'] = mk(C, vl[(1, 1)], {'Producto': D('sales de baño aromaticas', 'TIPOGRAFICO', 'Sales de baño aromáticas')})
w['2'] = mk(C, vl[(2, 0)], {'Fecha': D('4/10/2026', FH, '2026-10-04'), 'Cantidad': D('', 'NULO', '1 (total ÷ precio unitario)'), 'Precio unit.': D('42,50', 'TIPO_DATO', '42.50')})
w['3a'] = mk(C, vl[(3, 0)], {'Fecha': D('05-10-26', FH, '2026-10-05'), 'Producto': D('Exfoliante corporal de cafe', 'TIPOGRAFICO', 'Exfoliante corporal de café'),
             'Precio unit.': D('S/ 45', 'TIPO_DATO', '45.00'), 'Total venta': D('S/ 80.00', 'INCONSISTENCIA', '83.00 (suma de cantidad × precio de sus líneas)')})
w['3b'] = mk(C, {**vl[(3, 1)], 'Total venta': 'S/ 80.00', 'Fecha': '05-10-26'}, {'Precio unit.': D('38', 'TIPO_DATO', '38.00')})
w['3b'].inj = [i for i in w['3b'].inj if i[0] != 'Precio unit.']   # "38" es válido; no se cuenta como error
w['4a'] = mk(C, vl[(4, 0)], {'Cantidad': D('3 und', 'TIPO_DATO', '3')})
w['4b'] = mk(C, vl[(4, 1)], {'Precio unit.': D('9,50', 'TIPO_DATO', '9.50')})
w['5a'] = mk(C, vl[(5, 0)], {'Fecha': D('7 de octubre de 2026', FH, '2026-10-07'), 'Precio unit.': D('S/. 48.00', 'TIPO_DATO', '48.00'), 'Total venta': D('104,00', 'TIPO_DATO', '104.00')})
w['5b'] = mk(C, {**vl[(5, 1)], 'Fecha': '7 de octubre de 2026', 'Total venta': '104,00'}, {'Producto': D('toallas descartables', 'TIPOGRAFICO', 'Toallas descartables')})
w['6'] = mk(C, vl[(6, 0)], {'Precio unit.': D('S/ 32', 'TIPO_DATO', '32.00')})
rows = [w['1a'], w['1b'], w['2'], w['3a'], w['3b'], w['4a'], w['4b'], dup(w['4b'], None, 'copia exacta de la fila'), w['5a'], w['5b'], blank(6), w['6'], footer(6, 'Total del período: S/ 420.00')]
n_vent = write_source('ventas.csv', C, rows)

# ------------------------------------------------------------------ PEDIDOS
C = ['N° pedido', 'Fecha', 'Proveedor', 'Producto', 'Cantidad', 'Precio unit.', 'Registrado por']
def cp(pd, k):
    pr, cant, p = pd[4][k]
    return {'N° pedido': str(pd[0]), 'Fecha': pe(pd[1]), 'Proveedor': PROV[pd[3]][1], 'Producto': PRD[pr][1], 'Cantidad': str(cant), 'Precio unit.': money(p), 'Registrado por': USU[pd[2]][0]}
pl = {(p[0], k): cp(p, k) for p in PEDIDOS for k in range(len(p[4]))}
z = {}
z['1a'] = mk(C, pl[(1, 0)], {'Proveedor': D('Aromas del Peru EIRL', 'TIPOGRAFICO', 'Aromas del Perú E.I.R.L.'), 'Cantidad': D('20 und', 'TIPO_DATO', '20'), 'Precio unit.': D('S/ 24.00', 'TIPO_DATO', '24.00'),
             'Registrado por': D('Jorge Mendoza Caceres', 'TIPOGRAFICO', 'Jorge Mendoza Cáceres')})
z['1b'] = mk(C, pl[(1, 1)], {'Precio unit.': D('17,50', 'TIPO_DATO', '17.50')})
z['2a'] = mk(C, pl[(2, 0)], {'Fecha': D('22-09-26', FH, '2026-09-22'), 'Proveedor': D('DISTRIBUIDORA COSMETICA ANDINA SAC', 'TIPOGRAFICO', 'Distribuidora Cosmética Andina S.A.C.'),
             'Precio unit.': D('S/ 29', 'TIPO_DATO', '29.00'), 'Registrado por': D('JORGE MENDOZA CÁCERES', 'TIPOGRAFICO', 'Jorge Mendoza Cáceres')})
z['2b'] = mk(C, pl[(2, 1)], {'Producto': D('Mascarilla de arcilla berde', 'TIPOGRAFICO', 'Mascarilla de arcilla verde')})
z['2c'] = mk(C, pl[(2, 2)], {'Precio unit.': D('S/ 34.00', 'TIPO_DATO', '34.00')})
z['3a'] = mk(C, pl[(3, 0)], {'Fecha': D('1 de octubre de 2026', FH, '2026-10-01'), 'Precio unit.': D('S/ 19', 'TIPO_DATO', '19.00')})
z['3b'] = mk(C, pl[(3, 1)], {'Producto': D('removedor de esmalte', 'TIPOGRAFICO', 'Removedor de esmalte'), 'Cantidad': D('30 und', 'TIPO_DATO', '30'), 'Precio unit.': D('6,50', 'TIPO_DATO', '6.50')})
z['3c'] = mk(C, pl[(3, 2)], {'Fecha': D('', 'NULO', '2026-10-01 (se recupera de las otras líneas del mismo pedido)')})
z['4a'] = mk(C, pl[(4, 0)], {'Fecha': D('06.10.2026', FH, '2026-10-06'), 'Proveedor': D('Belleza Total Peru S.A.', 'TIPOGRAFICO', 'Belleza Total Perú S.A.'),
             'Precio unit.': D('S/ 22.00', 'TIPO_DATO', '22.00'), 'Registrado por': D('jorge mendoza caceres', 'TIPOGRAFICO', 'Jorge Mendoza Cáceres')})
z['4b'] = mk(C, pl[(4, 1)], {'Precio unit.': D('31,50', 'TIPO_DATO', '31.50')})
rows = [z['1a'], z['1b'], z['2a'], z['2b'], dup(z['2b'], None, 'copia exacta de la fila'), z['2c'], z['3a'], z['3b'], z['3c'], z['4a'], z['4b'], footer(7, 'Total de pedidos: 4')]
n_ped = write_source('pedidos.csv', C, rows)

# --------------------------------------------- ESPERADO (modelo físico, 18 tablas)
esp_names = []
for _, e in EMPLEADOS:
    if e not in esp_names: esp_names.append(e)
pref_names = []
for c in CLIENTES:
    for pf in c[6]:
        if pf not in pref_names: pref_names.append(pf)
write_gold('usuario.csv', ['id_usuario', 'nombre', 'telefono'], [(u, USU[u][0], USU[u][1]) for u in USU])
write_gold('especialidad.csv', ['id_especialidad', 'nombre_especialidad'], [(i + 1, n) for i, n in enumerate(esp_names)])
write_gold('empleado.csv', ['codigo_empleado', 'id_especialidad', 'id_usuario'], [(i + 1, esp_names.index(e) + 1, u) for i, (u, e) in enumerate(EMPLEADOS)])
write_gold('almacen.csv', ['codigo_almacen', 'id_usuario'], [(i + 1, u) for i, (_, u) in enumerate(ALMACENES)])
write_gold('cliente.csv', ['codigo_cliente', 'nombres', 'apellidos', 'calle', 'ciudad', 'id_usuario'], [(c[0], c[2], c[1], c[3], c[4], c[5]) for c in CLIENTES])
write_gold('preferencia.csv', ['id_preferencia', 'descripcion'], [(i + 1, n) for i, n in enumerate(pref_names)])
write_gold('cliente_preferencia.csv', ['codigo_cliente', 'id_preferencia'], [(c[0], pref_names.index(pf) + 1) for c in CLIENTES for pf in c[6]])
write_gold('estado_cita.csv', ['id_estado', 'descripcion'], [(i + 1, e) for i, e in enumerate(ESTADOS)])
write_gold('servicio.csv', ['codigo_servicio', 'nombre', 'descripcion', 'precio', 'duracion'], [(s[0], s[1], s[2], money(s[3]), s[4]) for s in SERVICIOS])
alm_id = {n: i + 1 for i, (n, _) in enumerate(ALMACENES)}
def stock_final(p):
    ent = sum(d[1] for pd in PEDIDOS for d in pd[4] if d[0] == p[0]); sal = sum(d[1] for v in VENTAS for d in v[2] if d[0] == p[0])
    return p[4] + ent - sal      # la fuente trae el stock INICIAL; los triggers suman pedidos y restan ventas
write_gold('producto.csv', ['codigo_producto', 'nombre', 'descripcion', 'precio_unitario', 'stock', 'codigo_almacen'], [(p[0], p[1], p[2], money(p[3]), stock_final(p), alm_id[p[5]]) for p in PRODUCTOS])
write_gold('servicio_producto.csv', ['codigo_servicio', 'codigo_producto', 'cantidad_usada'], INSUMOS)
write_gold('proveedor.csv', ['codigo_proveedor', 'razon_social', 'telefono', 'correo'], PROVEEDORES)
write_gold('pedido_compra.csv', ['id_pedido', 'fecha', 'id_usuario', 'codigo_proveedor'], [(p[0], p[1], p[2], p[3]) for p in PEDIDOS])
write_gold('detalle_pedido.csv', ['id_pedido', 'codigo_producto', 'cantidad', 'precio'], [(p[0], d[0], d[1], money(d[2])) for p in PEDIDOS for d in p[4]])
write_gold('venta.csv', ['numero_venta', 'fecha', 'total'], [(v[0], v[1], money(tot(v))) for v in VENTAS])
write_gold('detalle_venta.csv', ['numero_venta', 'codigo_producto', 'cantidad', 'precio'], [(v[0], d[0], d[1], money(d[2])) for v in VENTAS for d in v[2]])
def obs(c): return f'Cliente: {full(CLI[c[4]])}.' + (f' {c[8]}' if c[8] else '')
write_gold('cita.csv', ['numero_registro', 'fecha', 'hora_inicio', 'hora_fin', 'observaciones', 'id_estado', 'id_usuario'],
           [(c[0], c[1], c[2] + ':00', c[3] + ':00', obs(c), ESTADOS.index(c[6]) + 1, c[7]) for c in CITAS])
write_gold('cita_servicio.csv', ['numero_registro', 'codigo_servicio', 'precio'], [(c[0], s, money(p)) for c in CITAS for s, p in c[5]])

# --------------------------------------------------------------- DICCIONARIOS
def write_dic(name, values, alias=None):
    alias = alias or {}
    with open(os.path.join(BASE, 'diccionarios', name), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';'); w.writerow(['valor_valido', 'alias_conocidos'])
        for v in values: w.writerow([v, '|'.join(alias.get(v, []))])
DIC = {}
DIC['usuarios.csv'] = [USU[u][0] for u in USU]
DIC['estados_cita.csv'] = ESTADOS
DIC['especialidades.csv'] = esp_names
DIC['distritos.csv'] = sorted({c[4] for c in CLIENTES})
DIC['servicios.csv'] = [s[1] for s in SERVICIOS]
DIC['productos.csv'] = [p[1] for p in PRODUCTOS]
DIC['proveedores.csv'] = [p[1] for p in PROVEEDORES]
DIC['almacenes.csv'] = [a[0] for a in ALMACENES]
DIC['preferencias.csv'] = pref_names
DIC['clientes.csv'] = [f'{c[1]}, {c[2]}' for c in CLIENTES]
ALIAS = {'clientes.csv': {f'{c[1]}, {c[2]}': [full(c)] for c in CLIENTES},
         'distritos.csv': {'Santiago de Surco': ['Surco', 'Stgo. de Surco']},
         'estados_cita.csv': {'Atendida': ['Completada', 'Finalizada'], 'Pendiente': ['Por confirmar']},
         'proveedores.csv': {'Distribuidora Cosmética Andina S.A.C.': ['Distribuidora Cosmetica Andina SAC'],
                             'Aromas del Perú E.I.R.L.': ['Aromas del Peru EIRL'], 'Belleza Total Perú S.A.': ['Belleza Total Peru SA']}}
for n, vals in DIC.items(): write_dic(n, vals, ALIAS.get(n))

# ------------------------------------------------------------------- BITÁCORA
ap = WBS['Spa_Ventas_y_Pedidos.xlsx'].create_sheet('Resumen')
ap.cell(1, 1, 'Hoja de apoyo del spa (totales y notas): no contiene datos del modelo').font = Font(bold=True)
ap.cell(3, 1, 'Ventas del período'); ap.cell(3, 2, 420.00); ap.cell(4, 1, 'Pedidos del período'); ap.cell(4, 2, 4)
for libro, wb in WBS.items(): wb.save(os.path.join(BASE, 'excel_sucios', libro))
with open(os.path.join(BASE, 'bitacora_errores_sembrados.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f, delimiter=';'); w.writerow(['libro', 'hoja', 'fila_excel', 'columna', 'tipo_error', 'valor_sucio', 'valor_esperado', 'regla_aplicada'])
    for b in BIT: w.writerow([SRC_MAP[b[0]][0], SRC_MAP[b[0]][1], b[1]] + b[2:])

# ------------------------------------------------------------------ VERIFICACIÓN
def norm(s):
    s = unicodedata.normalize('NFKD', s.strip().lower()); s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return ' '.join(s.replace('.', '').split())
DIC_BY_COL = {('clientes.csv', 'Cliente'): 'clientes.csv', ('citas.csv', 'Cliente'): 'clientes.csv', ('personal.csv', 'Nombre'): 'usuarios.csv', ('personal.csv', 'Especialidad'): 'especialidades.csv', ('clientes.csv', 'Distrito'): 'distritos.csv',
              ('clientes.csv', 'Atendido por'): 'usuarios.csv', ('servicios.csv', 'Servicio'): 'servicios.csv', ('productos.csv', 'Producto'): 'productos.csv',
              ('productos.csv', 'Almacen'): 'almacenes.csv', ('insumos_servicio.csv', 'Servicio'): 'servicios.csv', ('insumos_servicio.csv', 'Producto'): 'productos.csv',
              ('proveedores.csv', 'Razon social'): 'proveedores.csv', ('almacenes.csv', 'Responsable'): 'usuarios.csv', ('citas.csv', 'Servicio'): 'servicios.csv',
              ('citas.csv', 'Estado'): 'estados_cita.csv', ('citas.csv', 'Registrada por'): 'usuarios.csv', ('ventas.csv', 'Producto'): 'productos.csv',
              ('pedidos.csv', 'Proveedor'): 'proveedores.csv', ('pedidos.csv', 'Producto'): 'productos.csv', ('pedidos.csv', 'Registrado por'): 'usuarios.csv'}
bad = []
for arch, fila, col, tipo, sucio, esp, _ in BIT:
    if tipo == 'TIPOGRAFICO' and (arch, col) in DIC_BY_COL:
        cands = DIC[DIC_BY_COL[(arch, col)]]; al = ALIAS.get(DIC_BY_COL[(arch, col)], {})
        pool = {norm(v): v for v in cands}
        for v, a in al.items():
            for x in a: pool[norm(x)] = v
        n = norm(sucio)
        if n in pool: ok = pool[n] == esp
        else:
            m = difflib.get_close_matches(n, list(pool), n=1, cutoff=0.88); ok = bool(m) and pool[m[0]] == esp
        if not ok: bad.append((arch, fila, col, sucio, esp))
print('hojas (filas):', dict(personal=n_personal, clientes=n_clientes, servicios=n_serv, productos=n_prod, insumos=n_ins, proveedores=n_prov, almacenes=n_alm, citas=n_citas, ventas=n_vent, pedidos=n_ped))
from collections import Counter
print('errores sembrados por tipo:', dict(Counter(b[3] for b in BIT)), 'total', len(BIT))
print('tipográficos NO recuperables con el diccionario:', bad if bad else 'ninguno')
