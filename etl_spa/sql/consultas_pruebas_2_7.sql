-- =====================================================================
-- SALÓN SPA RODRÍGUEZ — SECCIÓN 2.7: CONSULTAS Y PRUEBAS
-- Base de datos: spa_rodriguez (o spa_rodriguez_pruebas)
-- Compatible con MySQL 8.0.16+ / MariaDB 10.2.1+
--
-- NOTA IMPORTANTE PARA MYSQL WORKBENCH:
-- Dado que las pruebas de reglas de negocio (R1 a R10) fuerzan
-- deliberadamente violaciones de CHECK, FOREIGN KEY y TRIGGERS para
-- comprobar que el motor las rechaza, en MySQL Workbench se debe desactivar
-- "Stop Script Execution on Errors" (menú Query > Continue on SQL Script Error)
-- o bien ejecutar cada bloque de prueba individualmente.
-- Todas las pruebas que alteran datos se encuentran dentro de
-- bloques START TRANSACTION ... ROLLBACK para mantener los datos intactos.
-- =====================================================================

USE spa_rodriguez;
SET NAMES utf8mb4;

-- =====================================================================
-- BLOQUE I: CONSULTAS SQL PARA LA GESTIÓN DEL SALÓN SPA (C1 - C10)
-- =====================================================================

-- C1. Historial de citas por cliente
SELECT CONCAT(cl.nombres, ' ', cl.apellidos)                  AS cliente,
       c.numero_registro                                      AS cita,
       DATE_FORMAT(c.fecha, '%d/%m/%Y')                       AS fecha,
       CONCAT(TIME_FORMAT(c.hora_inicio, '%H:%i'), ' - ',
              COALESCE(TIME_FORMAT(c.hora_fin, '%H:%i'), '--')) AS horario,
       GROUP_CONCAT(s.nombre ORDER BY s.nombre SEPARATOR ', ') AS servicios,
       e.descripcion                                          AS estado,
       u.nombre                                               AS registrada_por
FROM cliente cl
LEFT JOIN cita c           ON c.observaciones LIKE CONCAT('Cliente: ', cl.nombres, ' ', cl.apellidos, '.%')
LEFT JOIN estado_cita e    ON e.id_estado = c.id_estado
LEFT JOIN usuario u        ON u.id_usuario = c.id_usuario
LEFT JOIN cita_servicio cs ON cs.numero_registro = c.numero_registro
LEFT JOIN servicio s       ON s.codigo_servicio = cs.codigo_servicio
GROUP BY cl.codigo_cliente, cl.nombres, cl.apellidos, c.numero_registro,
         c.fecha, c.hora_inicio, c.hora_fin, e.descripcion, u.nombre
ORDER BY cliente, c.fecha, c.hora_inicio;

-- C2. Servicios más solicitados
SELECT s.codigo_servicio,
       s.nombre                                                  AS servicio,
       COUNT(cs.numero_registro)                                 AS veces_solicitado,
       SUM(CASE WHEN e.descripcion = 'Atendida'  THEN 1 ELSE 0 END) AS atendidas,
       SUM(CASE WHEN e.descripcion = 'Cancelada' THEN 1 ELSE 0 END) AS canceladas
FROM servicio s
LEFT JOIN cita_servicio cs ON cs.codigo_servicio = s.codigo_servicio
LEFT JOIN cita c           ON c.numero_registro = cs.numero_registro
LEFT JOIN estado_cita e    ON e.id_estado = c.id_estado
GROUP BY s.codigo_servicio, s.nombre
ORDER BY veces_solicitado DESC, s.nombre;

-- C3. Ingresos estimados por servicios atendidos
SELECT COALESCE(s.nombre, 'TOTAL')    AS servicio,
       COUNT(*)                       AS atenciones,
       SUM(cs.precio)                 AS ingreso_estimado,
       SUM(s.precio)                  AS valor_precio_lista,
       SUM(s.precio) - SUM(cs.precio) AS diferencia
FROM cita_servicio cs
INNER JOIN cita c        ON c.numero_registro = cs.numero_registro
INNER JOIN estado_cita e ON e.id_estado = c.id_estado
INNER JOIN servicio s    ON s.codigo_servicio = cs.codigo_servicio
WHERE e.descripcion = 'Atendida'
GROUP BY s.nombre WITH ROLLUP;

-- C4. Estado general de las citas
SELECT e.id_estado,
       e.descripcion                 AS estado,
       COUNT(c.numero_registro)      AS cantidad_citas,
       ROUND(100 * COUNT(c.numero_registro) / (SELECT COUNT(*) FROM cita), 1) AS porcentaje
FROM estado_cita e
LEFT JOIN cita c ON c.id_estado = e.id_estado
GROUP BY e.id_estado, e.descripcion
ORDER BY e.id_estado;

-- C5. Productos con menor stock
SELECT p.codigo_producto,
       p.nombre                         AS producto,
       p.stock,
       p.codigo_almacen,
       u.nombre                         AS responsable_almacen,
       (SELECT COUNT(*) FROM servicio_producto sp
         WHERE sp.codigo_producto = p.codigo_producto) AS servicios_que_lo_usan,
       ROUND((SELECT AVG(stock) FROM producto), 1)     AS stock_promedio
FROM producto p
INNER JOIN almacen a ON a.codigo_almacen = p.codigo_almacen
INNER JOIN usuario u ON u.id_usuario = a.id_usuario
ORDER BY p.stock ASC, p.nombre
LIMIT 5;

-- C6. Productos más vendidos
SELECT p.codigo_producto,
       p.nombre                                   AS producto,
       COALESCE(SUM(dv.cantidad), 0)              AS unidades_vendidas,
       COUNT(DISTINCT dv.numero_venta)            AS num_ventas,
       COALESCE(SUM(dv.cantidad * dv.precio), 0)  AS importe,
       DATE_FORMAT(MAX(v.fecha), '%d/%m/%Y')      AS ultima_venta
FROM producto p
LEFT JOIN detalle_venta dv ON dv.codigo_producto = p.codigo_producto
LEFT JOIN venta v          ON v.numero_venta = dv.numero_venta
GROUP BY p.codigo_producto, p.nombre
ORDER BY unidades_vendidas DESC, importe DESC, p.nombre
LIMIT 5;

-- C7. Total de ventas registradas
-- (a) Por fecha con total general
SELECT COALESCE(DATE_FORMAT(v.fecha, '%d/%m/%Y'), 'TOTAL') AS fecha,
       COUNT(*)     AS num_ventas,
       SUM(v.total) AS monto_vendido
FROM venta v
GROUP BY v.fecha WITH ROLLUP;

-- (b) Resumen mensual con ticket promedio
SELECT YEAR(v.fecha)          AS anio,
       MONTH(v.fecha)         AS mes,
       COUNT(*)               AS num_ventas,
       SUM(v.total)           AS monto_vendido,
       ROUND(AVG(v.total), 2) AS ticket_promedio
FROM venta v
GROUP BY YEAR(v.fecha), MONTH(v.fecha)
ORDER BY anio, mes;

-- C8. Historial de pedidos a proveedores
-- (a) Detalle de los pedidos de compra
SELECT pc.id_pedido,
       DATE_FORMAT(pc.fecha, '%d/%m/%Y') AS fecha,
       pr.razon_social                   AS proveedor,
       p.nombre                          AS producto,
       dp.cantidad,
       dp.precio                         AS precio_compra,
       dp.cantidad * dp.precio           AS subtotal,
       u.nombre                          AS solicitado_por
FROM pedido_compra pc
INNER JOIN proveedor pr      ON pr.codigo_proveedor = pc.codigo_proveedor
INNER JOIN usuario u         ON u.id_usuario = pc.id_usuario
INNER JOIN detalle_pedido dp ON dp.id_pedido = pc.id_pedido
INNER JOIN producto p        ON p.codigo_producto = dp.codigo_producto
ORDER BY pc.fecha, pc.id_pedido, p.nombre;

-- (b) Resumen acumulado por proveedor
SELECT pr.razon_social                              AS proveedor,
       COUNT(DISTINCT pc.id_pedido)                 AS pedidos,
       COALESCE(SUM(dp.cantidad), 0)                AS unidades,
       COALESCE(SUM(dp.cantidad * dp.precio), 0)    AS monto_comprado
FROM proveedor pr
LEFT JOIN pedido_compra pc   ON pc.codigo_proveedor = pr.codigo_proveedor
LEFT JOIN detalle_pedido dp  ON dp.id_pedido = pc.id_pedido
GROUP BY pr.codigo_proveedor, pr.razon_social
ORDER BY monto_comprado DESC;

-- C9. Clientes con mayor cantidad de citas
-- (a) Ranking general
SELECT CONCAT(cl.nombres, ' ', cl.apellidos)        AS cliente,
       COUNT(DISTINCT c.numero_registro)            AS total_citas,
       COUNT(DISTINCT CASE WHEN e.descripcion <> 'Cancelada'
                           THEN c.numero_registro END) AS citas_no_canceladas,
       COUNT(cs.codigo_servicio)                    AS servicios_reservados,
       DATE_FORMAT(MAX(c.fecha), '%d/%m/%Y')        AS ultima_cita
FROM cliente cl
INNER JOIN cita c          ON c.observaciones LIKE CONCAT('Cliente: ', cl.nombres, ' ', cl.apellidos, '.%')
INNER JOIN estado_cita e   ON e.id_estado = c.id_estado
LEFT JOIN cita_servicio cs ON cs.numero_registro = c.numero_registro
GROUP BY cl.codigo_cliente, cl.nombres, cl.apellidos
ORDER BY total_citas DESC, servicios_reservados DESC, cliente
LIMIT 5;

-- (b) Clientes recurrentes (> 1 cita)
SELECT CONCAT(cl.nombres, ' ', cl.apellidos) AS cliente,
       COUNT(DISTINCT c.numero_registro)     AS total_citas
FROM cliente cl
INNER JOIN cita c ON c.observaciones LIKE CONCAT('Cliente: ', cl.nombres, ' ', cl.apellidos, '.%')
GROUP BY cl.codigo_cliente, cl.nombres, cl.apellidos
HAVING COUNT(DISTINCT c.numero_registro) > 1
ORDER BY total_citas DESC, cliente;

-- C10. Consistencia de los totales de venta
-- (a) Comparación venta por venta
SELECT v.numero_venta,
       DATE_FORMAT(v.fecha, '%d/%m/%Y')                   AS fecha,
       COALESCE(d.lineas, 0)                              AS lineas,
       v.total                                            AS total_registrado,
       COALESCE(d.total_calculado, 0)                     AS total_calculado,
       v.total - COALESCE(d.total_calculado, 0)           AS diferencia,
       CASE WHEN v.total = COALESCE(d.total_calculado, 0)
            THEN 'Consistente' ELSE 'Descuadre' END       AS verificacion
FROM venta v
LEFT JOIN (SELECT numero_venta,
                  COUNT(*)               AS lineas,
                  SUM(cantidad * precio) AS total_calculado
           FROM detalle_venta
           GROUP BY numero_venta) d ON d.numero_venta = v.numero_venta
ORDER BY v.numero_venta;

-- (b) Total de descuadres
SELECT COUNT(*) AS ventas_con_descuadre
FROM venta v
WHERE v.total <> (SELECT COALESCE(SUM(d.cantidad * d.precio), 0)
                  FROM detalle_venta d
                  WHERE d.numero_venta = v.numero_venta);


-- =====================================================================
-- BLOQUE II: PRUEBAS DE REGLAS DE NEGOCIO Y RESTRICCIONES (R1 - R10)
-- =====================================================================

-- R1. Integridad referencial de las citas (FK fk_cita_usuario)
START TRANSACTION;
SELECT COUNT(*) AS existe_usuario_999 FROM usuario WHERE id_usuario = 999;
-- Esperado: Error 1452 (Cannot add or update a child row: foreign key constraint fails)
INSERT INTO cita (fecha, hora_inicio, hora_fin, observaciones, id_estado, id_usuario)
VALUES ('2026-10-20', '10:00:00', '11:00:00', 'Prueba R1', 1, 999);
ROLLBACK;
SELECT COUNT(*) AS citas_registradas FROM cita;

-- R2. Validez del estado de las citas (FK fk_cita_estado)
START TRANSACTION;
SELECT COUNT(*) AS existe_estado_99 FROM estado_cita WHERE id_estado = 99;
-- Esperado: Error 1452 (foreign key fk_cita_estado fails)
INSERT INTO cita (fecha, hora_inicio, hora_fin, observaciones, id_estado, id_usuario)
VALUES ('2026-10-20', '10:00:00', '11:00:00', 'Prueba R2', 99, 2);
ROLLBACK;
SELECT COUNT(*) AS citas_registradas FROM cita;

-- R3. Cantidades positivas en las ventas (CHECK detalle_venta_chk_1)
START TRANSACTION;
-- Esperado: Error 3819 (Check constraint 'detalle_venta_chk_1' is violated)
INSERT INTO detalle_venta (numero_venta, codigo_producto, cantidad, precio)
VALUES (1, 3, 0, 42.50);
-- Esperado: Error 3819
INSERT INTO detalle_venta (numero_venta, codigo_producto, cantidad, precio)
VALUES (1, 3, -2, 42.50);
ROLLBACK;
SELECT COUNT(*) AS lineas_venta_1 FROM detalle_venta WHERE numero_venta = 1;

-- R4. Precios válidos (CHECK producto_chk_1 y servicio_chk_1)
START TRANSACTION;
-- Esperado: Error 3819
INSERT INTO producto (nombre, descripcion, precio_unitario, stock, codigo_almacen)
VALUES ('Producto R4', 'Prueba', 0.00, 10, 1);
-- Esperado: Error 3819
INSERT INTO servicio (nombre, descripcion, precio, duracion)
VALUES ('Servicio R4', 'Prueba', -10.00, 30);
-- Esperado: Error 3819
UPDATE servicio SET precio = 0 WHERE codigo_servicio = 1;
ROLLBACK;
SELECT codigo_servicio, nombre, precio FROM servicio WHERE codigo_servicio = 1;

-- R5. Duración de los servicios (CHECK servicio_chk_2)
START TRANSACTION;
-- Esperado: Error 3819
INSERT INTO servicio (nombre, descripcion, precio, duracion)
VALUES ('Servicio R5', 'Prueba', 50.00, 0);
-- Esperado: Error 3819
UPDATE servicio SET duracion = -15 WHERE codigo_servicio = 1;
ROLLBACK;
SELECT codigo_servicio, nombre, duracion FROM servicio WHERE codigo_servicio = 1;

-- R6. Integridad de los productos (FK fk_producto_almacen)
START TRANSACTION;
SELECT COUNT(*) AS existe_almacen_99 FROM almacen WHERE codigo_almacen = 99;
-- Esperado: Error 1452
INSERT INTO producto (nombre, descripcion, precio_unitario, stock, codigo_almacen)
VALUES ('Producto R6', 'Prueba', 20.00, 5, 99);
ROLLBACK;
SELECT COUNT(*) AS productos_registrados FROM producto;

-- R7. Validación de teléfonos (CHECK chk_usuario_telefono y VARCHAR(9))
START TRANSACTION;
-- Esperado: Error 3819 (longitud menor a 9 dígitos)
INSERT INTO usuario (nombre, telefono) VALUES ('Prueba R7-a', '12345');
-- Esperado: Error 3819 (contiene letras)
INSERT INTO usuario (nombre, telefono) VALUES ('Prueba R7-b', '98765432A');
-- Esperado: Error 3819 (formato con guion)
UPDATE proveedor SET telefono = '987-10010' WHERE codigo_proveedor = 1;
-- Esperado: Error 1406 (longitud excede 9 caracteres en modo estricto)
INSERT INTO usuario (nombre, telefono) VALUES ('Prueba R7-c', '9876543210');
-- Control positivo: teléfono válido
INSERT INTO usuario (nombre, telefono) VALUES ('Prueba R7-d', '987111222');
SELECT nombre, telefono FROM usuario WHERE nombre LIKE 'Prueba R7%';
ROLLBACK;
SELECT COUNT(*) AS usuarios_registrados FROM usuario;

-- R8. Prevención de ventas sin stock (TRIGGER trg_detalle_venta_descuenta_stock)
START TRANSACTION;
SELECT codigo_producto, nombre, stock FROM producto WHERE codigo_producto = 3;
-- Esperado: Error 1644 (Stock insuficiente para completar la venta)
INSERT INTO detalle_venta (numero_venta, codigo_producto, cantidad, precio)
VALUES (6, 3, 999, 42.50);
SELECT p.stock, v.total AS total_venta_6
FROM producto p, venta v
WHERE p.codigo_producto = 3 AND v.numero_venta = 6;
ROLLBACK;

-- R9. Integridad referencial de los proveedores (FK fk_pedido_proveedor y fk_detped_pedido)
START TRANSACTION;
SELECT COUNT(*) AS existe_proveedor_99 FROM proveedor WHERE codigo_proveedor = 99;
-- Esperado: Error 1452
INSERT INTO pedido_compra (fecha, id_usuario, codigo_proveedor)
VALUES ('2026-10-20', 6, 99);
-- Esperado: Error 1452
INSERT INTO detalle_pedido (id_pedido, codigo_producto, cantidad, precio)
VALUES (99, 1, 10, 24.00);
ROLLBACK;
SELECT COUNT(*) AS pedidos_registrados FROM pedido_compra;

-- R10. Eliminación y relaciones dependientes (CASCADE vs RESTRICT)
START TRANSACTION;
-- (a) ON DELETE CASCADE: cliente -> cliente_preferencia
SELECT COUNT(*) AS preferencias_cliente_1 FROM cliente_preferencia WHERE codigo_cliente = 1;
DELETE FROM cliente WHERE codigo_cliente = 1;
SELECT COUNT(*) AS preferencias_cliente_1 FROM cliente_preferencia WHERE codigo_cliente = 1;

-- (b) ON DELETE CASCADE: cita -> cita_servicio
SELECT COUNT(*) AS servicios_cita_6 FROM cita_servicio WHERE numero_registro = 6;
DELETE FROM cita WHERE numero_registro = 6;
SELECT COUNT(*) AS servicios_cita_6 FROM cita_servicio WHERE numero_registro = 6;

-- (c) ON DELETE RESTRICT: usuario referenciado por almacen (Esperado: Error 1451)
DELETE FROM usuario WHERE id_usuario = 6;

-- (d) ON DELETE RESTRICT: producto referenciado por detalle_pedido (Esperado: Error 1451)
DELETE FROM producto WHERE codigo_producto = 1;

-- (e) ON DELETE RESTRICT: preferencia usada por cliente_preferencia (Esperado: Error 1451)
DELETE FROM preferencia WHERE id_preferencia = 3;
ROLLBACK;
SELECT (SELECT COUNT(*) FROM cliente)             AS clientes,
       (SELECT COUNT(*) FROM cliente_preferencia) AS cliente_preferencia,
       (SELECT COUNT(*) FROM cita)                AS citas,
       (SELECT COUNT(*) FROM cita_servicio)       AS cita_servicio;


-- =====================================================================
-- PRUEBAS COMPLEMENTARIAS: REGLAS NO IMPLEMENTADAS EN EL ESQUEMA (N1, N2)
-- =====================================================================

-- N1. Demostración de ausencia de RN-02 (Cruce de horarios de citas)
START TRANSACTION;
INSERT INTO cita (fecha, hora_inicio, hora_fin, observaciones, id_estado, id_usuario)
VALUES ('2026-10-20', '10:00:00', '11:00:00', 'Prueba N1-a', 1, 2);
INSERT INTO cita (fecha, hora_inicio, hora_fin, observaciones, id_estado, id_usuario)
VALUES ('2026-10-20', '10:30:00', '11:30:00', 'Prueba N1-b', 1, 2);
SELECT a.numero_registro AS cita_a, b.numero_registro AS cita_b, a.id_usuario,
       a.hora_inicio AS inicio_a, a.hora_fin AS fin_a, b.hora_inicio AS inicio_b, b.hora_fin AS fin_b
FROM cita a
INNER JOIN cita b ON b.id_usuario = a.id_usuario AND b.fecha = a.fecha
                 AND a.numero_registro < b.numero_registro
                 AND a.hora_inicio < b.hora_fin AND b.hora_inicio < a.hora_fin;
ROLLBACK;

-- N2. Demostración de ausencia de RN-06 (Venta sin al menos un ítem)
START TRANSACTION;
INSERT INTO venta (fecha) VALUES ('2026-10-20');
SELECT v.numero_venta, v.total, COUNT(d.codigo_producto) AS lineas_detalle
FROM venta v LEFT JOIN detalle_venta d ON d.numero_venta = v.numero_venta
WHERE v.numero_venta = LAST_INSERT_ID()
GROUP BY v.numero_venta, v.total;
ROLLBACK;


-- =====================================================================
-- BLOQUE III: COMPROBACIÓN DE TRIGGERS Y CONTROL DE INVENTARIO (S1 - S4)
-- =====================================================================

-- S1. Descuento automático del stock por una venta (RN-07)
START TRANSACTION;
SELECT codigo_producto, nombre, stock AS stock_inicial FROM producto WHERE codigo_producto = 3;
INSERT INTO venta (fecha) VALUES ('2026-10-20');
SET @v := LAST_INSERT_ID();
INSERT INTO detalle_venta (numero_venta, codigo_producto, cantidad, precio)
VALUES (@v, 3, 2, 42.50);
SELECT codigo_producto, nombre, stock AS stock_final FROM producto WHERE codigo_producto = 3;
ROLLBACK;
SELECT stock AS stock_tras_rollback FROM producto WHERE codigo_producto = 3;

-- S2. Incremento del stock por un pedido de compra
START TRANSACTION;
SELECT codigo_producto, nombre, stock AS stock_inicial FROM producto WHERE codigo_producto = 9;
INSERT INTO pedido_compra (fecha, id_usuario, codigo_proveedor) VALUES ('2026-10-20', 6, 4);
SET @p := LAST_INSERT_ID();
INSERT INTO detalle_pedido (id_pedido, codigo_producto, cantidad, precio)
VALUES (@p, 9, 10, 22.00);
SELECT codigo_producto, nombre, stock AS stock_final FROM producto WHERE codigo_producto = 9;
ROLLBACK;
SELECT stock AS stock_tras_rollback FROM producto WHERE codigo_producto = 9;

-- S3. Rechazo de una venta sin stock suficiente y caso límite (RN-08)
START TRANSACTION;
SELECT codigo_producto, nombre, stock AS stock_inicial FROM producto WHERE codigo_producto = 9;
INSERT INTO venta (fecha) VALUES ('2026-10-20');
SET @v := LAST_INSERT_ID();
-- (a) Intento de vender 27 con stock 26 (Esperado: Error 1644)
INSERT INTO detalle_venta (numero_venta, codigo_producto, cantidad, precio)
VALUES (@v, 9, 27, 32.00);
SELECT p.stock, v.total AS total_venta,
       (SELECT COUNT(*) FROM detalle_venta WHERE numero_venta = @v) AS lineas
FROM producto p, venta v
WHERE p.codigo_producto = 9 AND v.numero_venta = @v;
-- (b) Caso límite: vender exactamente el stock disponible (26)
INSERT INTO detalle_venta (numero_venta, codigo_producto, cantidad, precio)
VALUES (@v, 9, 26, 32.00);
SELECT stock FROM producto WHERE codigo_producto = 9;
-- (c) Con stock en 0, intentar vender 1 unidad (Esperado: Error 1644)
INSERT INTO venta (fecha) VALUES ('2026-10-20');
SET @v2 := LAST_INSERT_ID();
INSERT INTO detalle_venta (numero_venta, codigo_producto, cantidad, precio)
VALUES (@v2, 9, 1, 32.00);
ROLLBACK;
SELECT stock AS stock_tras_rollback FROM producto WHERE codigo_producto = 9;

-- S4. Actualización del total de una venta (dato derivado venta.total)
START TRANSACTION;
INSERT INTO venta (fecha) VALUES ('2026-10-20');
SET @v := LAST_INSERT_ID();
SELECT numero_venta, total AS total_inicial FROM venta WHERE numero_venta = @v;
INSERT INTO detalle_venta (numero_venta, codigo_producto, cantidad, precio)
VALUES (@v, 1, 2, 35.00);
INSERT INTO detalle_venta (numero_venta, codigo_producto, cantidad, precio)
VALUES (@v, 7, 1, 25.00);
SELECT v.numero_venta, v.total AS total_cabecera,
       (SELECT SUM(cantidad * precio) FROM detalle_venta
         WHERE numero_venta = v.numero_venta) AS suma_detalle
FROM venta v WHERE v.numero_venta = @v;
ROLLBACK;
SELECT COUNT(*) AS ventas_registradas FROM venta;

-- O1. Observación: eliminación de una línea de detalle en el esquema vigente
START TRANSACTION;
SELECT (SELECT stock FROM producto WHERE codigo_producto = 3) AS stock_prod_3,
       (SELECT total FROM venta WHERE numero_venta = 2)       AS total_venta_2;
DELETE FROM detalle_venta WHERE numero_venta = 2 AND codigo_producto = 3;
SELECT (SELECT stock FROM producto WHERE codigo_producto = 3) AS stock_prod_3,
       (SELECT total FROM venta WHERE numero_venta = 2)       AS total_venta_2,
       (SELECT COALESCE(SUM(cantidad * precio), 0) FROM detalle_venta
         WHERE numero_venta = 2)                              AS suma_detalle_2;
ROLLBACK;
