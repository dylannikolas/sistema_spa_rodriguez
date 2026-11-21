# ETL del Salón Spa Rodríguez — origen: libros Excel

**Datos simulados.** El caso no entrega datos reales: los libros de `excel_sucios/` se construyeron a partir de la población del modelo y se les sembraron errores a propósito (164, anotados en `bitacora_errores_sembrados.csv`). Debe declararse en el informe.

## Cómo ejecutarlo
1. MySQL 8.0.16+ (o MariaDB 10.2.1+) encendido y Python 3 con `pip install pymysql openpyxl`.
2. Copia `.env.example` a `.env` y pon tu usuario y contraseña.
3. `python etl_spa.py` (carga normal) o `python etl_spa.py --demo-cuarentena` (agrega 2 filas inválidas para mostrar la cuarentena).

El script crea la base `spa_rodriguez` solo si falta; si ya existe, retira los triggers y **vacía las tablas** (no borra la base). Código de salida 0 = todas las pruebas críticas PASS.

## Etapas (coinciden con los diagramas del informe)
Extracción (Excel → `csv_extraidos/`) · Transformación (→ `csv_limpios/`, sin tocar la base) · Fase 1 conexión y preparación del destino · Fase 2 validar los CSV · Fase 3 cargar con cuarentena · Fase 4 verificar · Fase 5 reglas de negocio · Fase 6 reporte.

## Contenido
| Elemento | Qué es |
|---|---|
| `excel_sucios/` | 4 libros .xlsx (10 hojas de datos + hoja de apoyo "Resumen") con títulos sobre la cabecera, celdas nativas (fecha, hora, número) mezcladas con texto sucio. |
| `diccionarios/` | Valores válidos y alias (usuarios, clientes, servicios, productos, proveedores, almacenes, distritos, especialidades, preferencias, estados). |
| `sql/spa_rodriguez.sql` | Solo estructura: 18 tablas, 19 llaves foráneas, CHECK, 2 triggers de stock y catálogo de estados. No borra datos. |
| `esperado/` | Resultado correcto de las 18 tablas (144 filas). `producto.stock` es el stock FINAL. |
| `csv_extraidos/`, `csv_limpios/` | Salidas de la extracción y de la transformación. |
| `cuarentena.csv`, `cuarentena_demo.csv` | Filas rechazadas (0 en la carga normal; 2 en la prueba con filas inválidas). |
| `reporte_etl.md`, `log_etl.txt`, `log_demo_cuarentena.txt` | Resultado de la última ejecución normal (94 PASS, 0 FAIL) y de la prueba de cuarentena. |
| `diagramas/` | Diagramas 0FN–3FN, flujos del ETL, capturas y sus generadores. |
| `generar_csv_sucios.py` | Regenera los libros Excel, esperados, diccionarios y bitácora. |

## Supuestos (revisar)
1. Almacén de cada producto: Principal (7) y Recepción (esmalte, removedor, toallas).
2. Como `cita` no tiene llave a `cliente`, el nombre del cliente se guarda en `observaciones`.
3. El modelo físico no tiene `cliente.telefono`: el ETL lo descarta aunque la fuente lo trae.
4. Estados de cita: Pendiente, Confirmada, Atendida, Cancelada ("Completada" es alias de "Atendida").
5. Probado en MariaDB 10.11.14; no se ejecutó en MySQL 8.0.
