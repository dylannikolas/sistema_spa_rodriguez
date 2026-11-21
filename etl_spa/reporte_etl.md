# Reporte del ETL — Salón Spa Rodríguez

| Fase | Prueba | Resultado | Detalle |
|---|---|---|---|
| EXT | Personal: cabecera en la fila 4; 9 filas × 4 columnas extraídas = 9 × 4 de la hoja | **PASS** |  |
| EXT | Clientes: cabecera en la fila 4; 11 filas × 6 columnas extraídas = 11 × 6 de la hoja | **PASS** |  |
| EXT | Almacenes: cabecera en la fila 4; 2 filas × 2 columnas extraídas = 2 × 2 de la hoja | **PASS** |  |
| EXT | Servicios: cabecera en la fila 4; 9 filas × 4 columnas extraídas = 9 × 4 de la hoja | **PASS** |  |
| EXT | Productos: cabecera en la fila 4; 11 filas × 5 columnas extraídas = 11 × 5 de la hoja | **PASS** |  |
| EXT | Insumos por servicio: cabecera en la fila 4; 20 filas × 3 columnas extraídas = 20 × 3 de la hoja | **PASS** |  |
| EXT | Proveedores: cabecera en la fila 4; 5 filas × 3 columnas extraídas = 5 × 3 de la hoja | **PASS** |  |
| EXT | Citas: cabecera en la fila 4; 16 filas × 11 columnas extraídas = 16 × 11 de la hoja | **PASS** |  |
| EXT | Ventas: cabecera en la fila 4; 13 filas × 6 columnas extraídas = 13 × 6 de la hoja | **PASS** |  |
| EXT | Pedidos: cabecera en la fila 4; 12 filas × 7 columnas extraídas = 12 × 7 de la hoja | **PASS** |  |
| TRF | Ningún valor quedó sin reconocer (revisión manual = 0) | **PASS** |  |
| TRF | CSV limpio usuario: 6 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio especialidad: 4 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio preferencia: 11 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio estado_cita: 4 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio proveedor: 4 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio servicio: 8 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio almacen: 2 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio empleado: 4 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio cliente: 8 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio cliente_preferencia: 12 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio producto: 10 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio cita: 10 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio cita_servicio: 12 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio servicio_producto: 19 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio pedido_compra: 4 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio detalle_pedido: 10 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio venta: 6 filas, igual a lo esperado | **PASS** |  |
| TRF | CSV limpio detalle_venta: 10 filas, igual a lo esperado | **PASS** |  |
| F1 | Conexión exitosa a localhost:3306 | **PASS** |  |
| F1 | Versión 8.0.42 aplica los CHECK (MySQL ≥ 8.0.16 / MariaDB ≥ 10.2.1) | **PASS** |  |
| F1 | Existen las 18 tablas del modelo físico | **PASS** | tablas=18 |
| F1 | Existen las 19 llaves foráneas | **PASS** | fks=19 |
| F1 | Destino preparado: triggers de stock retirados y tablas vacías (la estructura se conserva) | **PASS** | triggers=0, filas=0 |
| F2 | Los 18 CSV existen, son legibles (UTF-8), con encabezados iguales a las columnas, tipos válidos, obligatorios completos y sin claves repetidas | **PASS** |  |
| F3 | Carga completa sin filas rechazadas | **PASS** | 0 rechazadas |
| F4 | usuario: filas leídas (6) = insertadas (6) + rechazadas (0) | **PASS** |  |
| F4 | especialidad: filas leídas (4) = insertadas (4) + rechazadas (0) | **PASS** |  |
| F4 | preferencia: filas leídas (11) = insertadas (11) + rechazadas (0) | **PASS** |  |
| F4 | estado_cita: filas leídas (4) = insertadas (4) + rechazadas (0) | **PASS** |  |
| F4 | proveedor: filas leídas (4) = insertadas (4) + rechazadas (0) | **PASS** |  |
| F4 | servicio: filas leídas (8) = insertadas (8) + rechazadas (0) | **PASS** |  |
| F4 | almacen: filas leídas (2) = insertadas (2) + rechazadas (0) | **PASS** |  |
| F4 | empleado: filas leídas (4) = insertadas (4) + rechazadas (0) | **PASS** |  |
| F4 | cliente: filas leídas (8) = insertadas (8) + rechazadas (0) | **PASS** |  |
| F4 | cliente_preferencia: filas leídas (12) = insertadas (12) + rechazadas (0) | **PASS** |  |
| F4 | producto: filas leídas (10) = insertadas (10) + rechazadas (0) | **PASS** |  |
| F4 | cita: filas leídas (10) = insertadas (10) + rechazadas (0) | **PASS** |  |
| F4 | cita_servicio: filas leídas (12) = insertadas (12) + rechazadas (0) | **PASS** |  |
| F4 | servicio_producto: filas leídas (19) = insertadas (19) + rechazadas (0) | **PASS** |  |
| F4 | pedido_compra: filas leídas (4) = insertadas (4) + rechazadas (0) | **PASS** |  |
| F4 | detalle_pedido: filas leídas (10) = insertadas (10) + rechazadas (0) | **PASS** |  |
| F4 | venta: filas leídas (6) = insertadas (6) + rechazadas (0) | **PASS** |  |
| F4 | detalle_venta: filas leídas (10) = insertadas (10) + rechazadas (0) | **PASS** |  |
| F4 | Total: 144 leídas = 144 insertadas + 0 rechazadas | **PASS** |  |
| F4 | usuario: contenido idéntico al esperado | **PASS** |  |
| F4 | especialidad: contenido idéntico al esperado | **PASS** |  |
| F4 | preferencia: contenido idéntico al esperado | **PASS** |  |
| F4 | estado_cita: contenido idéntico al esperado | **PASS** |  |
| F4 | proveedor: contenido idéntico al esperado | **PASS** |  |
| F4 | servicio: contenido idéntico al esperado | **PASS** |  |
| F4 | almacen: contenido idéntico al esperado | **PASS** |  |
| F4 | empleado: contenido idéntico al esperado | **PASS** |  |
| F4 | cliente: contenido idéntico al esperado | **PASS** |  |
| F4 | cliente_preferencia: contenido idéntico al esperado | **PASS** |  |
| F4 | producto: contenido idéntico al esperado | **PASS** |  |
| F4 | cita: contenido idéntico al esperado | **PASS** |  |
| F4 | cita_servicio: contenido idéntico al esperado | **PASS** |  |
| F4 | servicio_producto: contenido idéntico al esperado | **PASS** |  |
| F4 | pedido_compra: contenido idéntico al esperado | **PASS** |  |
| F4 | detalle_pedido: contenido idéntico al esperado | **PASS** |  |
| F4 | venta: contenido idéntico al esperado | **PASS** |  |
| F4 | detalle_venta: contenido idéntico al esperado | **PASS** |  |
| F4 | Filas huérfanas = 0 en las 19 llaves foráneas | **PASS** | 0 |
| F4 | venta.total = suma de cantidad × precio de su detalle | **PASS** | 0 descuadres |
| F4 | cita.hora_fin = hora_inicio + duración de sus servicios | **PASS** | 0 descuadres |
| F4 | Stock final por producto = stock inicial + pedidos − ventas | **PASS** | 0 descuadres |
| F4 | Triggers de stock activos de nuevo | **PASS** |  |
| F5 | Ingresos y ventas coinciden con lo esperado (S/ 410.00 y S/ 420.00) | **PASS** | servicios=410.00, ventas=420.00 |
| F5 | CHECK: precio de detalle_venta ≤ 0 | **PASS** | rechazado con error 3819 (esperado) |
| F5 | CHECK: cantidad ≤ 0 en detalle_pedido | **PASS** | rechazado con error 3819 (esperado) |
| F5 | CHECK: teléfono de 9 dígitos | **PASS** | rechazado con error 3819 (esperado) |
| F5 | FK: cita con usuario inexistente | **PASS** | rechazado con error 1452 (esperado) |
| F5 | UNIQUE: estado de cita repetido | **PASS** | rechazado con error 1062 (esperado) |
| F5 | Trigger: venta mayor al stock disponible | **PASS** | rechazado con error 1644 (esperado) |
| F5 | CASCADE: al borrar un cliente se borran sus preferencias | **PASS** | 12 → 10 (revertido) |
| F5 | ROLLBACK dejó los datos intactos | **PASS** |  |
| DET | FECHA_HORA: se detectaron los 18 errores sembrados | **PASS** | 18/18 |
| DET | INCONSISTENCIA: se detectaron los 2 errores sembrados | **PASS** | 2/2 |
| DET | NULO: se detectaron los 12 errores sembrados | **PASS** | 12/12 |
| DET | TIPOGRAFICO: se detectaron los 60 errores sembrados | **PASS** | 60/60 |
| DET | TIPO_DATO: se detectaron los 53 errores sembrados | **PASS** | 53/53 |
| DET | Duplicados eliminados = sembrados | **PASS** | 11/11 |
| DET | Filas vacías y de resumen eliminadas = sembradas | **PASS** | 8/8 |

## Correcciones aplicadas (primeras 60)

| Hoja | Fila Excel | Columna | Tipo | Valor sucio | Valor limpio |
|---|---|---|---|---|---|
| Personal | 9 | (fila completa) | NULO | fila vacía | eliminada |
| Personal | 13 | (fila completa) | NULO | Total personal: 6 | eliminada |
| Personal | 12 | (fila completa) | DUPLICADO | repite la fila 6 | eliminada |
| Personal | 5 | Celular | TIPO_DATO | 987 654 321 | 987654321 |
| Personal | 5 | Especialidad | NULO |  | NULL |
| Personal | 6 | Nombre | TIPOGRAFICO | LUCIA PAREDES HUAMAN | Lucía Paredes Huamán |
| Personal | 6 | Celular | TIPO_DATO | 986-543-210 | 986543210 |
| Personal | 7 | Nombre | TIPOGRAFICO | carmen soto villanueva  | Carmen Soto Villanueva |
| Personal | 7 | Celular | TIPO_DATO | +51 985432109 | 985432109 |
| Personal | 7 | Especialidad | TIPOGRAFICO | esteticista facial | Esteticista facial |
| Personal | 8 | Nombre | TIPOGRAFICO | Marco Quispe  Ramos | Marco Quispe Ramos |
| Personal | 10 | Celular | NULO |  | NULL |
| Personal | 10 | Especialidad | TIPOGRAFICO | Manicura y Pedicura | Manicura y pedicura |
| Personal | 11 | Especialidad | NULO |  | NULL |
| Almacenes | 6 | Responsable | TIPOGRAFICO | rosa rodriguez salazar | Rosa Rodríguez Salazar |
| Clientes | 9 | (fila completa) | NULO | fila vacía | eliminada |
| Clientes | 10 | (fila completa) | DUPLICADO | repite la fila 11 | eliminada |
| Clientes | 10 | Distrito | NULO |  | San Borja |
| Clientes | 15 | (fila completa) | DUPLICADO | repite la fila 13 | eliminada |
| Clientes | 5 | Celular | TIPO_DATO | 999 111 222 | 999111222 |
| Clientes | 5 | Distrito | TIPOGRAFICO | miraflores | Miraflores |
| Clientes | 5 | Preferencias | TIPOGRAFICO | masajes relajantes,  Aromas de lavanda  | Masajes relajantes / Aromas de lavanda |
| Clientes | 6 | Cliente | TIPOGRAFICO | GOMEZ ROJAS, Patricia | Gómez Rojas, Patricia |
| Clientes | 6 | Atendido por | TIPOGRAFICO | lucia paredes huaman | Lucía Paredes Huamán |
| Clientes | 7 | Distrito | TIPOGRAFICO | Surco | Santiago de Surco |
| Clientes | 7 | Preferencias | TIPOGRAFICO | Manicura en gel / Citas por la tarde | Manicura en gel / Citas por la tarde |
| Clientes | 8 | Direccion | TIPOGRAFICO | Jr. Cusco  410  | Jr. Cusco 410 |
| Clientes | 11 | Celular | TIPO_DATO | 999-555-666 | 999555666 |
| Clientes | 12 | Celular | TIPO_DATO | 99966677 | NULL |
| Clientes | 12 | Preferencias | TIPOGRAFICO | Pedicura - Productos hipoalergénicos | Pedicura / Productos hipoalergénicos |
| Clientes | 14 | Cliente | TIPOGRAFICO | NUÑEZ PONCE, GABRIELA | Núñez Ponce, Gabriela |
| Clientes | 14 | Preferencias | TIPOGRAFICO | Exfoliacion corporal, Citas por la mañana | Exfoliación corporal / Citas por la mañana |
| Servicios | 13 | (fila completa) | DUPLICADO | repite la fila 9 | eliminada |
| Servicios | 5 | Precio | TIPO_DATO | S/ 90.00 | 90.00 |
| Servicios | 5 | Duracion | TIPO_DATO | 60 min | 60 |
| Servicios | 6 | Precio | TIPO_DATO | S/110 | 110.00 |
| Servicios | 6 | Duracion | TIPO_DATO | 60 minutos | 60 |
| Servicios | 7 | Precio | TIPO_DATO | 120,00 | 120.00 |
| Servicios | 7 | Duracion | TIPO_DATO | 1 h 15 min | 75 |
| Servicios | 8 | Precio | TIPO_DATO | S/. 40 | 40.00 |
| Servicios | 8 | Duracion | TIPO_DATO | 45' | 45 |
| Servicios | 9 | Servicio | TIPOGRAFICO | Pedicura Spa | Pedicura spa |
| Servicios | 9 | Duracion | TIPO_DATO | 1 h | 60 |
| Servicios | 10 | Servicio | TIPOGRAFICO | EXFOLIACION CORPORAL | Exfoliación corporal |
| Servicios | 11 | Servicio | TIPOGRAFICO | Depilacion con cera | Depilación con cera |
| Servicios | 11 | Precio | TIPO_DATO | S/ 60 | 60.00 |
| Servicios | 12 | Descripcion | NULO |  | NULL |
| Productos | 15 | (fila completa) | DUPLICADO | repite la fila 9 | eliminada |
| Productos | 5 | Producto | TIPOGRAFICO | Aceite escencial de lavanda | Aceite esencial de lavanda |
| Productos | 5 | Precio | TIPO_DATO | S/ 35.00 | 35.00 |
| Productos | 5 | Almacen | TIPOGRAFICO | principal | Principal |
| Productos | 6 | Stock | TIPO_DATO | 18 und | 18 |
| Productos | 7 | Precio | TIPO_DATO | S/. 42,50 | 42.50 |
| Productos | 8 | Producto | TIPOGRAFICO | Mascarilla de arcilla berde | Mascarilla de arcilla verde |
| Productos | 8 | Almacen | TIPOGRAFICO | PRINCIPAL | Principal |
| Productos | 9 | Precio | TIPO_DATO |  S/ 18 | 18.00 |
| Productos | 9 | Almacen | TIPOGRAFICO | Recepcion | Recepción |
| Productos | 10 | Precio | TIPO_DATO | 9,50 | 9.50 |
| Productos | 10 | Stock | TIPO_DATO | 40 unid. | 40 |
| Productos | 10 | Almacen | TIPOGRAFICO | recepción | Recepción |
