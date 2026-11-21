-- =====================================================================
-- SALÓN SPA RODRÍGUEZ — Modelo físico (3FN) — MySQL 8.0.16+ / InnoDB
-- 18 tablas. Solo estructura, restricciones, triggers y catálogo de
-- estados (idempotente: no borra datos ni la base). Los datos los carga el
-- ETL (etl_spa.py) desde los libros Excel.
-- =====================================================================
CREATE DATABASE IF NOT EXISTS spa_rodriguez
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE spa_rodriguez;
SET NAMES utf8mb4;

-- ---------------------------------------------------------------------
-- 1. Catálogos y tablas sin dependencias
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuario (
  id_usuario INT AUTO_INCREMENT PRIMARY KEY,
  nombre     VARCHAR(100) NOT NULL,
  telefono   VARCHAR(9),
  CONSTRAINT chk_usuario_telefono CHECK (telefono REGEXP '^[0-9]{9}$')
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS especialidad (
  id_especialidad     INT AUTO_INCREMENT PRIMARY KEY,
  nombre_especialidad VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS estado_cita (
  id_estado   INT AUTO_INCREMENT PRIMARY KEY,
  descripcion VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS preferencia (
  id_preferencia INT AUTO_INCREMENT PRIMARY KEY,
  descripcion    VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS proveedor (
  codigo_proveedor INT AUTO_INCREMENT PRIMARY KEY,
  razon_social     VARCHAR(100) NOT NULL,
  telefono         VARCHAR(9),
  correo           VARCHAR(100),
  CONSTRAINT chk_proveedor_telefono CHECK (telefono REGEXP '^[0-9]{9}$')
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS servicio (
  codigo_servicio INT AUTO_INCREMENT PRIMARY KEY,
  nombre          VARCHAR(100) NOT NULL,
  descripcion     VARCHAR(255),
  precio          DECIMAL(10,2) NOT NULL CHECK (precio > 0),
  duracion        INT NOT NULL CHECK (duracion > 0)          -- minutos
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS venta (
  numero_venta INT AUTO_INCREMENT PRIMARY KEY,
  fecha        DATE NOT NULL,
  total        DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (total >= 0)   -- derivado: lo mantiene un trigger
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. Tablas que dependen de USUARIO
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS almacen (
  codigo_almacen INT AUTO_INCREMENT PRIMARY KEY,
  id_usuario     INT NOT NULL,
  CONSTRAINT fk_almacen_usuario FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS empleado (
  codigo_empleado INT AUTO_INCREMENT PRIMARY KEY,
  id_especialidad INT NOT NULL,
  id_usuario      INT NOT NULL,
  CONSTRAINT fk_empleado_especialidad FOREIGN KEY (id_especialidad) REFERENCES especialidad (id_especialidad)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_empleado_usuario FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS cliente (
  codigo_cliente INT AUTO_INCREMENT PRIMARY KEY,
  nombres        VARCHAR(100) NOT NULL,
  apellidos      VARCHAR(100) NOT NULL,
  calle          VARCHAR(150),
  ciudad         VARCHAR(80),
  id_usuario     INT NOT NULL,
  CONSTRAINT fk_cliente_usuario FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS cliente_preferencia (
  codigo_cliente INT NOT NULL,
  id_preferencia INT NOT NULL,
  PRIMARY KEY (codigo_cliente, id_preferencia),
  CONSTRAINT fk_clipref_cliente FOREIGN KEY (codigo_cliente) REFERENCES cliente (codigo_cliente)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_clipref_preferencia FOREIGN KEY (id_preferencia) REFERENCES preferencia (id_preferencia)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. Productos, citas y pedidos
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS producto (
  codigo_producto INT AUTO_INCREMENT PRIMARY KEY,
  nombre          VARCHAR(100) NOT NULL,
  descripcion     VARCHAR(255),
  precio_unitario DECIMAL(10,2) NOT NULL CHECK (precio_unitario > 0),
  stock           INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
  codigo_almacen  INT NOT NULL,
  CONSTRAINT fk_producto_almacen FOREIGN KEY (codigo_almacen) REFERENCES almacen (codigo_almacen)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS cita (
  numero_registro INT AUTO_INCREMENT PRIMARY KEY,
  fecha           DATE NOT NULL,
  hora_inicio     TIME NOT NULL,
  hora_fin        TIME,                                   -- derivado: hora_inicio + duración de los servicios
  observaciones   TEXT,
  id_estado       INT NOT NULL,
  id_usuario      INT NOT NULL,
  CONSTRAINT chk_cita_horas CHECK (hora_fin IS NULL OR hora_fin > hora_inicio),
  CONSTRAINT fk_cita_estado FOREIGN KEY (id_estado) REFERENCES estado_cita (id_estado)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_cita_usuario FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS cita_servicio (
  numero_registro INT NOT NULL,
  codigo_servicio INT NOT NULL,
  precio          DECIMAL(10,2) NOT NULL CHECK (precio > 0),
  PRIMARY KEY (numero_registro, codigo_servicio),
  CONSTRAINT fk_citaserv_cita FOREIGN KEY (numero_registro) REFERENCES cita (numero_registro)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_citaserv_servicio FOREIGN KEY (codigo_servicio) REFERENCES servicio (codigo_servicio)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS servicio_producto (
  codigo_servicio INT NOT NULL,
  codigo_producto INT NOT NULL,
  cantidad_usada  INT NOT NULL CHECK (cantidad_usada > 0),
  PRIMARY KEY (codigo_servicio, codigo_producto),
  CONSTRAINT fk_servprod_servicio FOREIGN KEY (codigo_servicio) REFERENCES servicio (codigo_servicio)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_servprod_producto FOREIGN KEY (codigo_producto) REFERENCES producto (codigo_producto)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pedido_compra (
  id_pedido        INT AUTO_INCREMENT PRIMARY KEY,
  fecha            DATE NOT NULL,
  id_usuario       INT NOT NULL,
  codigo_proveedor INT NOT NULL,
  CONSTRAINT fk_pedido_usuario FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_pedido_proveedor FOREIGN KEY (codigo_proveedor) REFERENCES proveedor (codigo_proveedor)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS detalle_pedido (
  id_pedido       INT NOT NULL,
  codigo_producto INT NOT NULL,
  cantidad        INT NOT NULL CHECK (cantidad > 0),
  precio          DECIMAL(10,2) NOT NULL CHECK (precio > 0),
  PRIMARY KEY (id_pedido, codigo_producto),
  CONSTRAINT fk_detped_pedido FOREIGN KEY (id_pedido) REFERENCES pedido_compra (id_pedido)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_detped_producto FOREIGN KEY (codigo_producto) REFERENCES producto (codigo_producto)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS detalle_venta (
  numero_venta    INT NOT NULL,
  codigo_producto INT NOT NULL,
  cantidad        INT NOT NULL CHECK (cantidad > 0),
  precio          DECIMAL(10,2) NOT NULL CHECK (precio > 0),
  PRIMARY KEY (numero_venta, codigo_producto),
  CONSTRAINT fk_detventa_venta FOREIGN KEY (numero_venta) REFERENCES venta (numero_venta)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_detventa_producto FOREIGN KEY (codigo_producto) REFERENCES producto (codigo_producto)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. Triggers de stock (RN-07 / RN-08) y total de venta
-- ---------------------------------------------------------------------
DELIMITER $$

DROP TRIGGER IF EXISTS trg_detalle_venta_descuenta_stock$$
CREATE TRIGGER trg_detalle_venta_descuenta_stock
AFTER INSERT ON detalle_venta
FOR EACH ROW
BEGIN
  DECLARE stock_actual INT;
  SELECT stock INTO stock_actual FROM producto
   WHERE codigo_producto = NEW.codigo_producto FOR UPDATE;
  IF stock_actual < NEW.cantidad THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Stock insuficiente para completar la venta';
  ELSE
    UPDATE producto SET stock = stock - NEW.cantidad WHERE codigo_producto = NEW.codigo_producto;
    UPDATE venta SET total = total + NEW.cantidad * NEW.precio WHERE numero_venta = NEW.numero_venta;
  END IF;
END$$

DROP TRIGGER IF EXISTS trg_detalle_pedido_aumenta_stock$$
CREATE TRIGGER trg_detalle_pedido_aumenta_stock
AFTER INSERT ON detalle_pedido
FOR EACH ROW
BEGIN
  UPDATE producto SET stock = stock + NEW.cantidad WHERE codigo_producto = NEW.codigo_producto;
END$$

DELIMITER ;

-- ---------------------------------------------------------------------
-- 5. Catálogo inicial del ciclo de vida de la cita (RN-04)
-- ---------------------------------------------------------------------
INSERT IGNORE INTO estado_cita (descripcion) VALUES ('Pendiente'), ('Confirmada'), ('Atendida'), ('Cancelada');
