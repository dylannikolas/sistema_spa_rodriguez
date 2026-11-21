-- =====================================================================================================
-- Salón Spa Rodríguez · Script SQL Unificado (Tablas de Seguridad, Bitácora y 7 Procedimientos SQL)
-- Base de datos: `spa_rodriguez` (MySQL 8.0 / InnoDB)
--
-- Contenido unificado en `spa_rodriguez`:
--   A) Tablas de autenticación y auditoría de la aplicación:
--      - `credencial`: usuarios, roles explícitos ('ADMIN', 'TRABAJADOR') y hashes PBKDF2-HMAC-SHA256.
--      - `bitacora`  : registro persistente de sesiones, bloqueos y operaciones sobre datos.
--   B) Los 7 Procedimientos Almacenados precompilados (`sp_*`):
--      1. `sp_registrar_venta`          : venta individual (delega stock y total al trigger).
--      2. `sp_registrar_venta_carrito`  : venta multiproducto atómica con JSON y bucle WHILE.
--      3. `sp_registrar_pedido_compra`  : orden de compra a proveedor (exclusivo rol ADMIN).
--      4. `sp_descontar_botella_cabina` : descuento de -1 unidad agotada en cabina estética.
--      5. `sp_cambiar_estado_cita`      : ciclo de vida RN-04 y control de propiedad por trabajador.
--      6. `sp_registrar_cita`           : cálculo de hora_fin (< 24:00) y bloqueo de solapamientos.
--      7. `sp_registrar_cliente`        : registro de cliente con preferencia exclusiva del catálogo 3FN.
--
-- Instalación: ejecutar mediante `python setup_procedimientos.py` o directamente en MySQL Workbench.
-- =====================================================================================================

USE spa_rodriguez;
SET NAMES utf8mb4;

-- =====================================================================================================
-- A. TABLAS DE AUTENTICACIÓN SEGURA (PBKDF2) Y BITÁCORA PERSISTENTE EN `spa_rodriguez`
-- =====================================================================================================
CREATE TABLE IF NOT EXISTS credencial (
    id_usuario        INT PRIMARY KEY,
    username          VARCHAR(50) NOT NULL UNIQUE,
    rol               ENUM('ADMIN', 'TRABAJADOR') NOT NULL DEFAULT 'TRABAJADOR',
    hash_clave        VARCHAR(128) NOT NULL,
    salt              VARCHAR(64) NOT NULL,
    iteraciones       INT NOT NULL CHECK (iteraciones >= 200000),
    activo            TINYINT(1) NOT NULL DEFAULT 1,
    debe_cambiar      TINYINT(1) NOT NULL DEFAULT 1,
    intentos_fallidos INT NOT NULL DEFAULT 0,
    bloqueado_hasta   DATETIME NULL,
    ultimo_acceso     DATETIME NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS bitacora (
    id_bitacora INT AUTO_INCREMENT PRIMARY KEY,
    fecha_hora  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    id_usuario  INT NULL,
    username    VARCHAR(60) NULL,
    accion      VARCHAR(80) NOT NULL,
    detalle     VARCHAR(500) NOT NULL
) ENGINE=InnoDB;

-- =====================================================================================================
-- B. PROCEDIMIENTOS ALMACENADOS PRECOMPILADOS (`sp_*`) EN `spa_rodriguez`
-- =====================================================================================================
DELIMITER $$

-- 1. Venta individual de producto (T1, T2)
DROP PROCEDURE IF EXISTS sp_registrar_venta$$
CREATE PROCEDURE sp_registrar_venta(
    IN p_codigo_producto INT,
    IN p_cantidad INT,
    OUT p_numero_venta INT,
    OUT p_nombre_producto VARCHAR(120),
    OUT p_total DECIMAL(10,2)
)
BEGIN
  DECLARE v_precio DECIMAL(10,2);
  DECLARE v_stock INT;
  SET p_numero_venta = NULL;
  SET p_nombre_producto = NULL;
  SET p_total = NULL;

  IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Validacion SQL (RN-06): La cantidad a vender debe ser un entero mayor a 0.';
  END IF;

  SELECT nombre, precio_unitario, stock INTO p_nombre_producto, v_precio, v_stock
    FROM producto WHERE codigo_producto = p_codigo_producto FOR UPDATE;

  IF p_nombre_producto IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Validacion SQL: El producto seleccionado no existe en el catalogo.';
  END IF;

  IF v_stock < p_cantidad THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Validacion SQL (RN-08): Stock insuficiente para realizar la venta.';
  END IF;

  -- El total inicia en 0 y lo acumula trg_detalle_venta_descuenta_stock
  INSERT INTO venta (fecha) VALUES (CURDATE());
  SET p_numero_venta = LAST_INSERT_ID();

  -- El trigger AFTER INSERT en detalle_venta descuenta el stock y suma el total
  INSERT INTO detalle_venta (numero_venta, codigo_producto, cantidad, precio)
  VALUES (p_numero_venta, p_codigo_producto, p_cantidad, v_precio);

  SELECT total INTO p_total FROM venta WHERE numero_venta = p_numero_venta;
END$$

-- 2. Venta de carrito con múltiples productos en una sola operación (T10)
DROP PROCEDURE IF EXISTS sp_registrar_venta_carrito$$
CREATE PROCEDURE sp_registrar_venta_carrito(
    IN p_lineas_json JSON,
    OUT p_numero_venta INT,
    OUT p_total DECIMAL(10,2)
)
BEGIN
  DECLARE v_n INT DEFAULT 0;
  DECLARE v_i INT DEFAULT 0;
  DECLARE v_cod_prod INT;
  DECLARE v_cant INT;
  DECLARE v_precio DECIMAL(10,2);
  DECLARE v_stock INT;
  DECLARE v_nombre VARCHAR(120);

  SET p_numero_venta = NULL;
  SET p_total = NULL;

  IF p_lineas_json IS NULL OR JSON_TYPE(p_lineas_json) <> 'ARRAY' OR JSON_LENGTH(p_lineas_json) = 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Validacion SQL: El carrito de venta debe contener al menos un producto.';
  END IF;

  SET v_n = JSON_LENGTH(p_lineas_json);

  INSERT INTO venta (fecha) VALUES (CURDATE());
  SET p_numero_venta = LAST_INSERT_ID();

  WHILE v_i < v_n DO
    SET v_cod_prod = CAST(JSON_UNQUOTE(JSON_EXTRACT(p_lineas_json, CONCAT('$[', v_i, '].codigo_producto'))) AS UNSIGNED);
    SET v_cant = CAST(JSON_UNQUOTE(JSON_EXTRACT(p_lineas_json, CONCAT('$[', v_i, '].cantidad'))) AS SIGNED);
    SET v_nombre = NULL;
    SET v_precio = NULL;
    SET v_stock = NULL;

    IF v_cant IS NULL OR v_cant <= 0 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Validacion SQL (RN-06): Todas las cantidades del carrito deben ser enteros mayores a 0.';
    END IF;

    SELECT nombre, precio_unitario, stock INTO v_nombre, v_precio, v_stock
      FROM producto WHERE codigo_producto = v_cod_prod FOR UPDATE;

    IF v_nombre IS NULL THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Validacion SQL: Uno de los productos del carrito no existe en el catalogo.';
    END IF;

    IF v_stock < v_cant THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Validacion SQL (RN-08): Stock insuficiente para uno de los productos del carrito.';
    END IF;

    INSERT INTO detalle_venta (numero_venta, codigo_producto, cantidad, precio)
    VALUES (p_numero_venta, v_cod_prod, v_cant, v_precio);

    SET v_i = v_i + 1;
  END WHILE;

  SELECT total INTO p_total FROM venta WHERE numero_venta = p_numero_venta;
END$$

-- 3. Pedido de compra a proveedor (T1, T2)
DROP PROCEDURE IF EXISTS sp_registrar_pedido_compra$$
CREATE PROCEDURE sp_registrar_pedido_compra(
    IN p_id_usuario_admin INT,
    IN p_codigo_proveedor INT,
    IN p_codigo_producto INT,
    IN p_cantidad INT,
    IN p_costo_unitario DECIMAL(10,2),
    OUT p_id_pedido INT
)
BEGIN
  SET p_id_pedido = NULL;

  IF EXISTS (SELECT 1 FROM empleado WHERE id_usuario = p_id_usuario_admin)
     OR EXISTS (SELECT 1 FROM credencial WHERE id_usuario = p_id_usuario_admin AND rol <> 'ADMIN') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Seguridad RBAC: Solo un usuario con rol Administrador puede emitir ordenes de compra a proveedores.';
  END IF;

  IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Validacion SQL (RN-06): La cantidad del lote debe ser mayor a 0.';
  END IF;

  IF p_costo_unitario IS NULL OR p_costo_unitario <= 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Validacion SQL (RN-09): El costo unitario de compra debe ser mayor a S/ 0.00.';
  END IF;

  INSERT INTO pedido_compra (fecha, id_usuario, codigo_proveedor)
  VALUES (CURDATE(), p_id_usuario_admin, p_codigo_proveedor);
  SET p_id_pedido = LAST_INSERT_ID();

  -- El trigger trg_detalle_pedido_aumenta_stock incrementa el stock automáticamente
  INSERT INTO detalle_pedido (id_pedido, codigo_producto, cantidad, precio)
  VALUES (p_id_pedido, p_codigo_producto, p_cantidad, ROUND(p_costo_unitario, 2));
END$$

-- 4. Descuento de unidad agotada por consumo interno en cabina (T1, T2)
DROP PROCEDURE IF EXISTS sp_descontar_botella_cabina$$
CREATE PROCEDURE sp_descontar_botella_cabina(
    IN p_codigo_producto INT,
    OUT p_nombre_producto VARCHAR(120),
    OUT p_stock_restante INT
)
BEGIN
  DECLARE v_stock INT;
  SET p_nombre_producto = NULL;
  SET p_stock_restante = NULL;

  SELECT nombre, stock INTO p_nombre_producto, v_stock
    FROM producto WHERE codigo_producto = p_codigo_producto FOR UPDATE;

  IF p_nombre_producto IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Validacion SQL (RN-07): El insumo seleccionado no existe en el inventario.';
  END IF;

  IF v_stock < 1 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Regla de Negocio (RN-07 / RN-08): El producto no tiene existencias; no se puede descontar.';
  END IF;

  -- Aquí no hay trigger porque es consumo interno en cabina, no venta
  UPDATE producto SET stock = stock - 1 WHERE codigo_producto = p_codigo_producto;
  SET p_stock_restante = v_stock - 1;
END$$

-- 5. Cambio de estado de cita con control de ciclo de vida y propiedad (T7)
-- p_id_usuario: NULL = administración (sin restricción); con valor = solo puede cambiar sus propias citas
DROP PROCEDURE IF EXISTS sp_cambiar_estado_cita$$
CREATE PROCEDURE sp_cambiar_estado_cita(
    IN p_numero_registro INT,
    IN p_nuevo_estado VARCHAR(40),
    IN p_id_usuario INT
)
BEGIN
  DECLARE v_estado_actual VARCHAR(40);
  DECLARE v_resp INT;

  SELECT e.descripcion, c.id_usuario INTO v_estado_actual, v_resp
    FROM cita c
    JOIN estado_cita e ON e.id_estado = c.id_estado
   WHERE c.numero_registro = p_numero_registro
   FOR UPDATE;

  IF v_estado_actual IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Validacion SQL (RN-04): La cita seleccionada no existe.';
  END IF;

  IF p_id_usuario IS NOT NULL AND v_resp <> p_id_usuario THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Seguridad RBAC: Solo puede cambiar el estado de sus propias citas.';
  END IF;

  IF NOT ((v_estado_actual = 'Pendiente' AND p_nuevo_estado IN ('Confirmada', 'Cancelada'))
       OR (v_estado_actual = 'Confirmada' AND p_nuevo_estado IN ('Atendida', 'Cancelada'))) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Regla de Negocio (RN-04): Transicion no permitida (Pendiente -> Confirmada/Cancelada; Confirmada -> Atendida/Cancelada).';
  END IF;

  UPDATE cita
     SET id_estado = (SELECT id_estado FROM estado_cita WHERE descripcion = p_nuevo_estado)
   WHERE numero_registro = p_numero_registro;
END$$

-- 6. Registro de cita con validación de horario (< 24:00) y no solapamiento (T8)
DROP PROCEDURE IF EXISTS sp_registrar_cita$$
CREATE PROCEDURE sp_registrar_cita(
    IN p_fecha DATE,
    IN p_hora_inicio TIME,
    IN p_codigo_servicio INT,
    IN p_observaciones VARCHAR(255),
    IN p_id_usuario INT,
    OUT p_numero_registro INT
)
BEGIN
  DECLARE v_precio DECIMAL(10,2);
  DECLARE v_duracion INT;
  DECLARE v_fin_seg INT;
  DECLARE v_estado INT;
  DECLARE v_cancelada INT;

  SET p_numero_registro = NULL;

  SELECT precio, duracion INTO v_precio, v_duracion
    FROM servicio WHERE codigo_servicio = p_codigo_servicio;

  IF v_duracion IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Validacion SQL: El servicio seleccionado no existe en el catalogo.';
  END IF;

  SET v_fin_seg = TIME_TO_SEC(p_hora_inicio) + v_duracion * 60;
  IF v_fin_seg >= 86400 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Validacion SQL: La cita terminaria despues de las 24:00; elija una hora de inicio mas temprana.';
  END IF;

  SELECT id_estado INTO v_cancelada FROM estado_cita WHERE descripcion = 'Cancelada';
  IF EXISTS (
      SELECT 1 FROM cita c
       WHERE c.id_usuario = p_id_usuario
         AND c.fecha = p_fecha
         AND c.id_estado <> v_cancelada
         AND TIME_TO_SEC(p_hora_inicio) < TIME_TO_SEC(c.hora_fin)
         AND v_fin_seg > TIME_TO_SEC(c.hora_inicio)
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Regla de Negocio: El usuario ya tiene otra cita que se superpone en ese horario.';
  END IF;

  SELECT id_estado INTO v_estado FROM estado_cita WHERE descripcion = 'Pendiente';
  INSERT INTO cita (fecha, hora_inicio, hora_fin, observaciones, id_estado, id_usuario)
  VALUES (
      p_fecha,
      p_hora_inicio,
      SEC_TO_TIME(v_fin_seg),
      NULLIF(TRIM(COALESCE(p_observaciones, '')), ''),
      v_estado,
      p_id_usuario
  );
  SET p_numero_registro = LAST_INSERT_ID();

  INSERT INTO cita_servicio (numero_registro, codigo_servicio, precio)
  VALUES (p_numero_registro, p_codigo_servicio, v_precio);
END$$

-- 7. Registro de cliente con preferencia exclusiva del catálogo oficial (T9)
DROP PROCEDURE IF EXISTS sp_registrar_cliente$$
CREATE PROCEDURE sp_registrar_cliente(
    IN p_nombres VARCHAR(80),
    IN p_apellidos VARCHAR(80),
    IN p_calle VARCHAR(120),
    IN p_ciudad VARCHAR(60),
    IN p_preferencia VARCHAR(120),
    IN p_id_usuario INT,
    OUT p_codigo_cliente INT
)
BEGIN
  DECLARE v_nom VARCHAR(80);
  DECLARE v_ape VARCHAR(80);
  DECLARE v_id_pref INT DEFAULT NULL;

  SET p_codigo_cliente = NULL;
  SET v_nom = TRIM(COALESCE(p_nombres, ''));
  SET v_ape = TRIM(COALESCE(p_apellidos, ''));

  IF CHAR_LENGTH(v_nom) < 2 OR CHAR_LENGTH(v_ape) < 2 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Validacion SQL: Los nombres y apellidos son obligatorios (minimo 2 caracteres).';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM usuario WHERE id_usuario = p_id_usuario) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Validacion SQL: El usuario operador indicado no existe.';
  END IF;

  IF TRIM(COALESCE(p_preferencia, '')) <> '' THEN
    SELECT id_preferencia INTO v_id_pref
      FROM preferencia WHERE descripcion = TRIM(p_preferencia) LIMIT 1;
    IF v_id_pref IS NULL THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Validacion SQL: La preferencia no existe en el catalogo; elijala de la lista.';
    END IF;
  END IF;

  INSERT INTO cliente (nombres, apellidos, calle, ciudad, id_usuario)
  VALUES (
      v_nom,
      v_ape,
      NULLIF(TRIM(COALESCE(p_calle, '')), ''),
      NULLIF(TRIM(COALESCE(p_ciudad, '')), ''),
      p_id_usuario
  );
  SET p_codigo_cliente = LAST_INSERT_ID();

  IF v_id_pref IS NOT NULL THEN
    INSERT IGNORE INTO cliente_preferencia (codigo_cliente, id_preferencia)
    VALUES (p_codigo_cliente, v_id_pref);
  END IF;
END$$

DELIMITER ;
