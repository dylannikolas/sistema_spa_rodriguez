# Salón Spa Rodríguez — Base de datos y sistema de gestión (`# sistema_spa_rodriguez`)

Proyecto del curso **Base de Datos II** (Universidad Nacional de Trujillo, Ingeniería Informática). Parte de un caso de negocio, el *Salón Spa Rodríguez*, y recorre todo el ciclo: diseño y normalización hasta 3FN, modelo físico en MySQL 8.0, carga de datos con un proceso ETL, consultas que comprueban las reglas de negocio y una aplicación de escritorio en Python con inicio de sesión por roles y procedimientos almacenados.

> Los datos del repositorio son **simulados**: el caso no entrega datos reales.

## Qué incluye

- **Diseño de la base de datos:** modelo entidad-relación, normalización paso a paso (0FN a 3FN) y modelo físico de **18 tablas** del negocio más **2 tablas de seguridad y auditoría** (`credencial` y `bitacora`) unificadas en `spa_rodriguez`.
- **Reglas de negocio en la base:** llaves foráneas (`FOREIGN KEY`), restricciones `CHECK` y triggers (`trg_detalle_venta_descuenta_stock` y `trg_detalle_pedido_aumenta_stock`) que descuentan el stock de las ventas, suman el de los pedidos y acumulan el total de cada venta sin duplicaciones.
- **ETL desde Excel (`etl_spa/`):** extracción de libros `.xlsx`, transformación (limpieza de tipografía, tipos de dato, fechas en formato local, nulos y duplicados), y carga por fases con verificación (94 pruebas PASS) y cuarentena de filas inválidas.
- **Consultas SQL y comprobación de reglas:** consultas de gestión y pruebas negativas que intentan violar las restricciones para verificar que la base las rechaza.
- **Aplicación de escritorio (Python + Tkinter):**
  - Inicio de sesión por `username`, con contraseñas protegidas (**PBKDF2-HMAC-SHA256** con `210 000` iteraciones y sal aleatoria por usuario) y bloqueo automático por 5 minutos tras 5 intentos fallidos.
  - Roles de usuario explícitos (`ADMIN` y `TRABAJADOR`) verificados tanto en la interfaz como en la capa de datos (`@requiere_rol`).
  - Operaciones de negocio mediante **7 procedimientos almacenados SQL precompilados** (`sp_registrar_venta`, `sp_registrar_venta_carrito`, `sp_registrar_pedido_compra`, `sp_descontar_botella_cabina`, `sp_cambiar_estado_cita`, `sp_registrar_cita`, `sp_registrar_cliente`).
  - Bitácora persistente de actividad (`bitacora`) y cambio obligatorio de la contraseña temporal en el primer ingreso.

## Tecnologías

Python 3 · Tkinter · MySQL 8.0 (InnoDB) · `mysql-connector-python` · PyMySQL · openpyxl · SQL (procedimientos almacenados, triggers, `SIGNAL SQLSTATE '45000'`, `JSON`).

## Estructura del repositorio

```text
├── etl_spa/                 Proceso ETL, libros Excel de origen, diccionarios, DDL base y reportes
│   ├── sql/spa_rodriguez.sql    Estructura de las 18 tablas del modelo físico y 2 triggers de stock
│   └── etl_spa.py               Script ETL de extracción, transformación, carga y verificación
├── sql/
│   └── procedimientos.sql   Script SQL unificado en spa_rodriguez (credencial, bitacora y 7 procedimientos sp_*)
├── ui/
│   └── portal_app.py        Interfaz gráfica por roles (Tkinter)
├── tests/
│   └── test_sistema_spa.py  Suite de 11 pruebas automáticas (unittest) sobre base aislada (spa_copia)
├── config.py                Configuración desde .env y diccionario centralizado de reglas (RN)
├── db.py                    Conexión transaccional a MySQL 8.0 sin DDL automático al iniciar
├── seguridad.py             Hash PBKDF2-HMAC-SHA256, sal criptográfica y política de contraseñas
├── permisos.py              Roles explícitos (ADMIN / TRABAJADOR) y decorador @requiere_rol
├── auth.py                  Autenticación segura, bloqueo por intentos y bitácora persistente
├── servicios.py             Operaciones del negocio e invocación de procedimientos (cur.callproc)
├── setup_procedimientos.py  Instalación única de sql/procedimientos.sql en spa_rodriguez
├── setup_auth.py            Inicialización de credenciales PBKDF2 y claves temporales
├── sistema_usuarios_spa.py  Punto de entrada principal de la aplicación
├── CAMBIOS.md               Detalle técnico de las mejoras y correcciones implementadas (T1 a T15)
└── .env.example             Plantilla de variables de entorno (sin secretos)
```

## Instalación y uso

1. **Requisitos:** Python 3.10 o superior y MySQL 8.0 encendido.
2. **Dependencias:**
   ```bash
   pip install mysql-connector-python pymysql openpyxl
   ```
3. **Configuración:** copia `.env.example` como `.env` y completa tus datos locales de MySQL.
   ```ini
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=tu_clave_mysql
   DB_NAME=spa_rodriguez
   DB_AUTH_NAME=spa_rodriguez
   ```
4. **Cargar la base de datos (ETL):**
   ```bash
   python etl_spa/etl_spa.py
   ```
5. **Instalar las tablas de seguridad y los 7 procedimientos almacenados:**
   ```bash
   python setup_procedimientos.py
   ```
6. **Crear las credenciales de los usuarios** (se genera una contraseña temporal aleatoria por usuario):
   ```bash
   python setup_auth.py
   ```
   Entrega cada clave temporal a su dueño y **borra el archivo generado (`credenciales_temporales_un_solo_uso.txt`)**. Cada usuario debe cambiarla obligatoriamente en su primer ingreso.
7. **Ejecutar la aplicación:**
   ```bash
   python sistema_usuarios_spa.py
   ```
8. **Ejecutar las pruebas automáticas:**
   ```bash
   python -m unittest discover -s tests -v
   ```

## Roles

| Rol | Qué puede hacer |
|---|---|
| **Administrador (`ADMIN`)** | Gestiona usuarios y roles, emite pedidos de compra a proveedores, administra productos/precios, ve y cambia el estado de todas las citas y consulta la bitácora persistente. |
| **Trabajador (`TRABAJADOR`)** | Registra clientes (con preferencias del catálogo oficial) y citas, cambia el estado solo de sus propias citas, registra ventas (individuales o por carrito) y descuenta insumos agotados en cabina. |

El rol se guarda de forma explícita en la tabla `credencial` (dentro de `spa_rodriguez`) y el proceso ETL conserva intactas las tablas `credencial` y `bitacora` al recargar las 18 tablas del modelo físico.

## Procedimientos almacenados SQL (`sql/procedimientos.sql`)

| Procedimiento | Función principal y reglas de negocio |
|---|---|
| `sp_registrar_venta` | Valida `cantidad > 0` (`RN-06`) y `stock >= cantidad` con bloqueo `FOR UPDATE` (`RN-08`), inserta en `venta` y `detalle_venta` y recupera el total calculado por el trigger (`RN-07`). |
| `sp_registrar_venta_carrito` | Registra una venta multiproducto desde un arreglo `JSON` usando un bucle `WHILE` en una sola operación atómica (todo o nada). |
| `sp_registrar_pedido_compra` | Verifica en SQL que el operador tenga rol `ADMIN` (`RN-02`), valida `cantidad > 0` y `costo > 0` (`RN-06`, `RN-09`) e inserta el pedido para que el trigger incremente el stock. |
| `sp_descontar_botella_cabina` | Descuenta `-1` unidad agotada por consumo interno en cabina estética (`RN-07`, `RN-08`). |
| `sp_cambiar_estado_cita` | Impone las transiciones válidas (`Pendiente → Confirmada/Cancelada`; `Confirmada → Atendida/Cancelada`, `RN-04`) y restringe a cada trabajador a sus propias citas. |
| `sp_registrar_cita` | Calcula `hora_fin` según la duración del servicio (`RN-05`), rechaza citas que terminen a las `24:00` o después y bloquea solapamientos horarios del mismo especialista. |
| `sp_registrar_cliente` | Valida nombres/apellidos (`>= 2` caracteres) y exige que la preferencia exista en el catálogo oficial `preferencia` (`RN-03`). |

## Límites del modelo

El modelo físico de 18 tablas no relaciona `cita` con `cliente`, `cliente` no tiene teléfono y `venta` no registra qué usuario la hizo. Para no alterar las 18 tablas del modelo del informe, el nombre del cliente se guarda estandarizado al inicio de las observaciones de la cita (`"Cliente: <nombres> <apellidos>."`) y la trazabilidad de las ventas queda registrada en `bitacora`.

## Seguridad: qué no subir a GitHub

El archivo `.gitignore` excluye automáticamente `.env`, `credenciales_temporales_un_solo_uso.txt` y cualquier archivo con contraseñas o datos sensibles.

## Autor

**Dylan Nikolas Jara Solorzano** — Ingeniería Informática, Universidad Nacional de Trujillo.  
Curso: Base de Datos II.

## Licencia

Proyecto académico.
