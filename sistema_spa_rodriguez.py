# -*- coding: utf-8 -*-
"""
SISTEMA DE GESTIÓN INTEGRAL — SALÓN SPA RODRÍGUEZ
Conectado a MySQL 8.0 / InnoDB (Configuración vía archivo .env)

Módulos incluidos:
  1. Dashboard Ejecutivo (Indicadores en tiempo real del negocio)
  2. Gestión de Usuarios y Personal: Agregar / Editar / Quitar Usuario (Administrador / Trabajador)
  3. Gestión de Clientes y Preferencias
  4. Gestión de Citas y Ciclo de Vida (Pendiente, Confirmada, Atendida, Cancelada)
  5. Inventario de Productos (Stock por botellas), Ventas y Pedidos a Proveedores
  6. Explorador Directo de las Tablas de la Base de Datos
"""
from __future__ import annotations

import os
import re
import sys
import datetime as dt
from decimal import Decimal
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import mysql.connector
from mysql.connector import Error as MySQLError

# ==============================================================================
# 1. CONFIGURACIÓN Y CONEXIÓN A LA BASE DE DATOS EN LA CARPETA ETL_SPA
# ==============================================================================
RUTA_PROYECTO_LOCAL = Path(__file__).resolve().parent
RUTA_ETL_USUARIO = RUTA_PROYECTO_LOCAL / "etl_spa"


def leer_env_archivo(ruta_env: Path) -> dict[str, str]:
    datos: dict[str, str] = {}
    if ruta_env.exists():
        for linea in ruta_env.read_text(encoding="utf-8", errors="replace").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            k, v = linea.split("=", 1)
            datos[k.strip()] = v.strip().strip('"').strip("'")
    return datos


def obtener_parametros_conexion() -> dict[str, object]:
    """Lee credenciales priorizando la carpeta etl_spa indicada por el usuario."""
    env_vars: dict[str, str] = {}
    for candidato in [
        RUTA_ETL_USUARIO / ".env",
        RUTA_PROYECTO_LOCAL / "etl_spa" / ".env",
        RUTA_PROYECTO_LOCAL / ".env",
    ]:
        if candidato.exists():
            env_vars.update(leer_env_archivo(candidato))
            break

    host = os.environ.get("DB_HOST", env_vars.get("DB_HOST", "localhost")).strip() or "localhost"
    port_str = os.environ.get("DB_PORT", env_vars.get("DB_PORT", "3306")).strip() or "3306"
    user = os.environ.get("DB_USER", env_vars.get("DB_USER", "root")).strip() or "root"
    password = os.environ.get("DB_PASSWORD", env_vars.get("DB_PASSWORD", ""))
    # Preferimos spa_rodriguez (que contiene la entidad USUARIO y EMPLEADO del modelo vigente)
    db_default = "spa_rodriguez"
    return {
        "host": host,
        "port": int(port_str),
        "user": user,
        "password": password,
        "database": db_default,
    }


class GestorBaseDatos:
    """Capa de acceso a datos compatible con el esquema de 16 tablas (spa_rodriguez)
    y el esquema de 18 tablas en 3FN (spa_rodriguez_pruebas)."""

    def __init__(self, params: dict[str, object]):
        self.params = dict(params)
        self.conn: mysql.connector.MySQLConnection | None = None
        self.tablas_disponibles: set[str] = set()
        self.columnas_por_tabla: dict[str, list[str]] = {}
        self.conectar(str(self.params.get("database", "spa_rodriguez")))

    def listar_bases_spa(self) -> list[str]:
        """Lista las bases de datos del proyecto disponibles en el servidor MySQL."""
        cfg_sin_db = {k: v for k, v in self.params.items() if k != "database"}
        conn_tmp = mysql.connector.connect(
            **cfg_sin_db, charset="utf8mb4", use_unicode=True, connection_timeout=8
        )
        try:
            cur = conn_tmp.cursor()
            cur.execute("SHOW DATABASES")
            todas = [r[0] for r in cur.fetchall()]
            preferidas = [db for db in todas if "spa" in db.lower()]
            # Asegurar que spa_rodriguez aparezca primero
            preferidas.sort(key=lambda x: (0 if x == "spa_rodriguez" else (1 if "pruebas" in x else 2), x))
            return preferidas or todas
        finally:
            conn_tmp.close()

    def conectar(self, nombre_bd: str) -> None:
        if self.conn is not None and self.conn.is_connected():
            try:
                self.conn.close()
            except MySQLError:
                pass

        bases = self.listar_bases_spa()
        if nombre_bd not in bases and bases:
            nombre_bd = bases[0]

        self.params["database"] = nombre_bd
        self.conn = mysql.connector.connect(
            host=self.params["host"],
            port=self.params["port"],
            user=self.params["user"],
            password=self.params["password"],
            database=nombre_bd,
            charset="utf8mb4",
            use_unicode=True,
            autocommit=False,
            connection_timeout=10,
        )
        self.inspeccionar_esquema()

    def asegurar_conexion(self) -> mysql.connector.MySQLConnection:
        if self.conn is None or not self.conn.is_connected():
            self.conectar(str(self.params.get("database", "spa_rodriguez")))
        assert self.conn is not None
        return self.conn

    def inspeccionar_esquema(self) -> None:
        conn = self.asegurar_conexion()
        cur = conn.cursor()
        cur.execute("SHOW TABLES")
        self.tablas_disponibles = {r[0] for r in cur.fetchall()}
        self.columnas_por_tabla.clear()
        for t in self.tablas_disponibles:
            cur.execute(f"DESCRIBE `{t}`")
            self.columnas_por_tabla[t] = [r[0] for r in cur.fetchall()]

        # Garantizar que la tabla usuario tenga las columnas username y contrasena
        if "usuario" in self.tablas_disponibles:
            cols_usr = self.columnas_por_tabla.get("usuario", [])
            if "username" not in cols_usr:
                try:
                    cur.execute("ALTER TABLE usuario ADD COLUMN username VARCHAR(50) NULL AFTER nombre")
                    conn.commit()
                    self.columnas_por_tabla["usuario"].append("username")
                except Exception:
                    pass
            if "contrasena" not in cols_usr:
                try:
                    cur.execute("ALTER TABLE usuario ADD COLUMN contrasena VARCHAR(255) NOT NULL DEFAULT 'spa123'")
                    conn.commit()
                    self.columnas_por_tabla["usuario"].append("contrasena")
                except Exception:
                    pass
            # Asignar user por defecto si algún registro está vacío
            try:
                cur.execute("SELECT id_usuario, nombre, COALESCE(username, '') FROM usuario")
                for uid, unom, uname_actual in cur.fetchall():
                    if not str(uname_actual or "").strip():
                        sug = self.generar_username_sugerido(str(unom), "Administrador" if uid in (1, 6) else "Trabajador")
                        cur.execute("UPDATE usuario SET username = %s WHERE id_usuario = %s", (sug, uid))
                conn.commit()
            except Exception:
                pass
        cur.close()

    @staticmethod
    def generar_username_sugerido(nombre: str, rol: str = "Trabajador") -> str:
        import unicodedata
        limpio = "".join(
            c for c in unicodedata.normalize("NFD", nombre.strip().lower()) if unicodedata.category(c) != "Mn"
        )
        partes = [re.sub(r"[^a-z0-9]", "", p) for p in limpio.split() if p]
        base = partes[0] if partes else "usuario"
        sufijo = "admin" if rol == "Administrador" else "spa"
        return f"{base}.{sufijo}"

    def consultar(self, sql: str, params: tuple | list | None = None) -> list[dict]:
        conn = self.asegurar_conexion()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(sql, params or ())
            filas = cur.fetchall()
            conn.commit()
            return filas
        finally:
            cur.close()

    def ejecutar(self, sql: str, params: tuple | list | None = None, commit: bool = True) -> int:
        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            cur.execute(sql, params or ())
            last_id = cur.lastrowid or 0
            if commit:
                conn.commit()
            return last_id
        except Exception:
            if commit:
                conn.rollback()
            raise
        finally:
            cur.close()

    def tiene_catalogo_especialidad(self) -> bool:
        return (
            "especialidad" in self.tablas_disponibles
            and "id_especialidad" in self.columnas_por_tabla.get("empleado", [])
        )

    def tiene_cliente_nombres_separados(self) -> bool:
        return "nombres" in self.columnas_por_tabla.get("cliente", [])

    def tiene_producto_almacen(self) -> bool:
        return "codigo_almacen" in self.columnas_por_tabla.get("producto", [])

    # ------------------------------------------------------------------
    # LÓGICA DE USUARIOS Y PERSONAL (ADMINISTRADOR / TRABAJADOR)
    # ------------------------------------------------------------------
    def listar_especialidades(self) -> list[str]:
        if self.tiene_catalogo_especialidad():
            filas = self.consultar("SELECT nombre_especialidad FROM especialidad ORDER BY nombre_especialidad")
            lista = [f["nombre_especialidad"] for f in filas if f.get("nombre_especialidad")]
        elif "empleado" in self.tablas_disponibles:
            filas = self.consultar(
                "SELECT DISTINCT especialidad FROM empleado WHERE especialidad IS NOT NULL AND especialidad <> '' ORDER BY especialidad"
            )
            lista = [f["especialidad"] for f in filas if f.get("especialidad")]
        else:
            lista = []
        base = [
            "Masajista terapéutica",
            "Esteticista facial",
            "Masajista deportivo",
            "Manicura y pedicura",
            "Depilación",
            "Cosmiatría facial",
            "Aromaterapia",
        ]
        for esp in base:
            if esp not in lista:
                lista.append(esp)
        return lista

    def obtener_usuarios_detallados(self, filtro_rol: str = "TODOS", busqueda: str = "") -> list[dict]:
        """Devuelve todos los usuarios indicando su username (user), si son Administrador o Trabajador,
        su especialidad (si son trabajadores), almacenes asignados y conteo de operaciones."""
        if "usuario" not in self.tablas_disponibles:
            return []

        if self.tiene_catalogo_especialidad():
            sql = """
                SELECT u.id_usuario,
                       u.nombre,
                       COALESCE(u.username, '') AS username,
                       COALESCE(u.telefono, '') AS telefono,
                       COALESCE(u.contrasena, 'spa123') AS contrasena,
                       GROUP_CONCAT(DISTINCT e.codigo_empleado ORDER BY e.codigo_empleado SEPARATOR ', ') AS codigos_empleado,
                       GROUP_CONCAT(DISTINCT esp.nombre_especialidad ORDER BY esp.nombre_especialidad SEPARATOR ', ') AS especialidad,
                       GROUP_CONCAT(DISTINCT a.codigo_almacen ORDER BY a.codigo_almacen SEPARATOR ', ') AS almacenes,
                       (SELECT COUNT(*) FROM cliente c WHERE c.id_usuario = u.id_usuario) AS total_clientes,
                       (SELECT COUNT(*) FROM cita ci WHERE ci.id_usuario = u.id_usuario) AS total_citas,
                       (SELECT COUNT(*) FROM pedido_compra p WHERE p.id_usuario = u.id_usuario) AS total_pedidos
                FROM usuario u
                LEFT JOIN empleado e ON e.id_usuario = u.id_usuario
                LEFT JOIN especialidad esp ON esp.id_especialidad = e.id_especialidad
                LEFT JOIN almacen a ON a.id_usuario = u.id_usuario
                GROUP BY u.id_usuario, u.nombre, u.username, u.telefono, u.contrasena
                ORDER BY u.id_usuario
            """
        else:
            sql = """
                SELECT u.id_usuario,
                       u.nombre,
                       COALESCE(u.username, '') AS username,
                       COALESCE(u.telefono, '') AS telefono,
                       COALESCE(u.contrasena, 'spa123') AS contrasena,
                       GROUP_CONCAT(DISTINCT e.codigo_empleado ORDER BY e.codigo_empleado SEPARATOR ', ') AS codigos_empleado,
                       GROUP_CONCAT(DISTINCT e.especialidad ORDER BY e.especialidad SEPARATOR ', ') AS especialidad,
                       GROUP_CONCAT(DISTINCT a.codigo_almacen ORDER BY a.codigo_almacen SEPARATOR ', ') AS almacenes,
                       (SELECT COUNT(*) FROM cliente c WHERE c.id_usuario = u.id_usuario) AS total_clientes,
                       (SELECT COUNT(*) FROM cita ci WHERE ci.id_usuario = u.id_usuario) AS total_citas,
                       (SELECT COUNT(*) FROM pedido_compra p WHERE p.id_usuario = u.id_usuario) AS total_pedidos
                FROM usuario u
                LEFT JOIN empleado e ON e.id_usuario = u.id_usuario
                LEFT JOIN almacen a ON a.id_usuario = u.id_usuario
                GROUP BY u.id_usuario, u.nombre, u.username, u.telefono, u.contrasena
                ORDER BY u.id_usuario
            """

        filas = self.consultar(sql)
        resultado = []
        q = busqueda.strip().lower()
        for f in filas:
            es_trabajador = bool(f.get("codigos_empleado"))
            rol = "Trabajador" if es_trabajador else "Administrador"
            f["rol"] = rol
            f["username"] = (f.get("username") or "").strip() or self.generar_username_sugerido(f["nombre"], rol)
            f["contrasena"] = f.get("contrasena") or ("admin123" if rol == "Administrador" else "spa123")
            f["especialidad_mostrar"] = f.get("especialidad") or ("Administración / Gestión" if not es_trabajador else "Sin especialidad")
            f["almacenes_mostrar"] = f"Almacén #{f['almacenes']}" if f.get("almacenes") else "—"

            if filtro_rol == "ADMINISTRADOR" and rol != "Administrador":
                continue
            if filtro_rol == "TRABAJADOR" and rol != "Trabajador":
                continue
            if q:
                texto = f"{f['id_usuario']} {f['username']} {f['nombre']} {f['telefono']} {rol} {f['especialidad_mostrar']}".lower()
                if q not in texto:
                    continue
            resultado.append(f)
        return resultado

    def _obtener_o_crear_id_especialidad(self, cur, nombre_esp: str) -> int:
        cur.execute("SELECT id_especialidad FROM especialidad WHERE nombre_especialidad = %s", (nombre_esp,))
        fila = cur.fetchone()
        if fila:
            return int(fila[0])
        cur.execute("INSERT INTO especialidad (nombre_especialidad) VALUES (%s)", (nombre_esp,))
        return int(cur.lastrowid)

    def agregar_usuario(
        self,
        nombre: str,
        telefono: str | None,
        rol: str,
        especialidad: str = "",
        registrar_almacen: bool = False,
        contrasena: str = "",
        username: str = "",
    ) -> int:
        """Agrega un nuevo usuario como Administrador o como Trabajador con su username y contraseña asignados."""
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El nombre del usuario es obligatorio.")

        tel_limpio: str | None = (telefono or "").strip() or None
        if tel_limpio is not None and not re.fullmatch(r"[0-9]{9}", tel_limpio):
            raise ValueError("El teléfono debe tener exactamente 9 dígitos numéricos (formato peruano) o dejarse vacío.")

        usr_limpio = username.strip().lower() or self.generar_username_sugerido(nombre, rol)
        pwd_limpio = contrasena.strip() or ("admin123" if rol == "Administrador" else "spa123")

        if rol == "Trabajador" and not especialidad.strip():
            raise ValueError("Para el rol 'Trabajador' debe seleccionar o escribir una especialidad.")

        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO usuario (nombre, username, telefono, contrasena) VALUES (%s, %s, %s, %s)",
                (nombre, usr_limpio, tel_limpio, pwd_limpio),
            )
            id_usuario = int(cur.lastrowid)

            if rol == "Trabajador":
                esp_txt = especialidad.strip()
                if self.tiene_catalogo_especialidad():
                    id_esp = self._obtener_o_crear_id_especialidad(cur, esp_txt)
                    cur.execute(
                        "INSERT INTO empleado (id_especialidad, id_usuario) VALUES (%s, %s)",
                        (id_esp, id_usuario),
                    )
                else:
                    cur.execute(
                        "INSERT INTO empleado (especialidad, id_usuario) VALUES (%s, %s)",
                        (esp_txt, id_usuario),
                    )

            if registrar_almacen and "almacen" in self.tablas_disponibles:
                cur.execute("INSERT INTO almacen (id_usuario) VALUES (%s)", (id_usuario,))

            conn.commit()
            return id_usuario
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def actualizar_usuario(
        self,
        id_usuario: int,
        nombre: str,
        telefono: str | None,
        rol: str,
        especialidad: str = "",
        contrasena: str = "",
        username: str = "",
    ) -> None:
        """Actualiza los datos de un usuario, su user de login, contraseña y sincroniza su rol (Administrador <-> Trabajador)."""
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El nombre del usuario es obligatorio.")

        tel_limpio: str | None = (telefono or "").strip() or None
        if tel_limpio is not None and not re.fullmatch(r"[0-9]{9}", tel_limpio):
            raise ValueError("El teléfono debe tener exactamente 9 dígitos numéricos o dejarse vacío.")

        if rol == "Trabajador" and not especialidad.strip():
            raise ValueError("Para el rol 'Trabajador' debe indicar una especialidad.")

        usr_limpio = username.strip().lower() or self.generar_username_sugerido(nombre, rol)
        pwd_limpio = contrasena.strip()

        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            if pwd_limpio:
                cur.execute(
                    "UPDATE usuario SET nombre = %s, username = %s, telefono = %s, contrasena = %s WHERE id_usuario = %s",
                    (nombre, usr_limpio, tel_limpio, pwd_limpio, id_usuario),
                )
            else:
                cur.execute(
                    "UPDATE usuario SET nombre = %s, username = %s, telefono = %s WHERE id_usuario = %s",
                    (nombre, usr_limpio, tel_limpio, id_usuario),
                )
            cur.execute("SELECT codigo_empleado FROM empleado WHERE id_usuario = %s", (id_usuario,))
            empleados_actuales = [r[0] for r in cur.fetchall()]

            if rol == "Administrador":
                if empleados_actuales:
                    cur.execute("DELETE FROM empleado WHERE id_usuario = %s", (id_usuario,))
            else:
                esp_txt = especialidad.strip()
                if self.tiene_catalogo_especialidad():
                    id_esp = self._obtener_o_crear_id_especialidad(cur, esp_txt)
                    if empleados_actuales:
                        cur.execute(
                            "UPDATE empleado SET id_especialidad = %s WHERE id_usuario = %s",
                            (id_esp, id_usuario),
                        )
                    else:
                        cur.execute(
                            "INSERT INTO empleado (id_especialidad, id_usuario) VALUES (%s, %s)",
                            (id_esp, id_usuario),
                        )
                else:
                    if empleados_actuales:
                        cur.execute(
                            "UPDATE empleado SET especialidad = %s WHERE id_usuario = %s",
                            (esp_txt, id_usuario),
                        )
                    else:
                        cur.execute(
                            "INSERT INTO empleado (especialidad, id_usuario) VALUES (%s, %s)",
                            (esp_txt, id_usuario),
                        )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def validar_login(self, identificador: str, contrasena: str) -> dict | None:
        """Valida credenciales por User (username), ID o Nombre y contraseña."""
        usuarios = self.obtener_usuarios_detallados()
        ident = identificador.strip().lower()
        pwd = contrasena.strip()
        for u in usuarios:
            coincide_user = u.get("username", "").lower() == ident
            coincide_id = str(u["id_usuario"]) == ident
            coincide_nom = u["nombre"].lower() == ident
            if (coincide_user or coincide_id or coincide_nom) and u.get("contrasena") == pwd:
                return u
        return None

    def obtener_dependencias_usuario(self, id_usuario: int) -> dict[str, int]:
        """Cuenta cuántos registros referencian a este usuario en tablas con ON DELETE RESTRICT."""
        deps: dict[str, int] = {}
        for tabla in ("cliente", "cita", "almacen", "pedido_compra"):
            if tabla in self.tablas_disponibles:
                filas = self.consultar(
                    f"SELECT COUNT(*) AS n FROM `{tabla}` WHERE id_usuario = %s",
                    (id_usuario,),
                )
                n = int(filas[0]["n"]) if filas else 0
                if n > 0:
                    deps[tabla] = n
        return deps

    def eliminar_usuario(self, id_usuario: int, id_usuario_reasignar: int | None = None) -> None:
        """Elimina un usuario (Administrador o Trabajador). Si tiene registros históricos
        en cliente/cita/almacen/pedido_compra y se indica id_usuario_reasignar, los reasigna
        antes de borrar para respetar la integridad referencial."""
        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            if id_usuario_reasignar is not None:
                if id_usuario_reasignar == id_usuario:
                    raise ValueError("El usuario de reasignación debe ser distinto al usuario que se va a eliminar.")
                for tabla in ("cliente", "cita", "almacen", "pedido_compra"):
                    if tabla in self.tablas_disponibles:
                        cur.execute(
                            f"UPDATE `{tabla}` SET id_usuario = %s WHERE id_usuario = %s",
                            (id_usuario_reasignar, id_usuario),
                        )

            if "empleado" in self.tablas_disponibles:
                cur.execute("DELETE FROM empleado WHERE id_usuario = %s", (id_usuario,))

            cur.execute("DELETE FROM usuario WHERE id_usuario = %s", (id_usuario,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


# ==============================================================================
# 2. INTERFAZ GRÁFICA DE USUARIO (TKINTER / TTK)
# ==============================================================================
COLOR_SIDEBAR = "#1B365D"
COLOR_SIDEBAR_BTN = "#244678"
COLOR_SIDEBAR_ACT = "#3B82F6"
COLOR_BG = "#F4F7FA"
COLOR_CARD = "#FFFFFF"
COLOR_PRIMARY = "#2E5B8A"
COLOR_SUCCESS = "#059669"
COLOR_DANGER = "#DC2626"
COLOR_WARNING = "#D97706"
COLOR_TEXT = "#1E293B"
COLOR_MUTED = "#64748B"


class SistemaSpaRodriguezApp(tk.Tk):
    def __init__(self, db: GestorBaseDatos):
        super().__init__()
        self.db = db
        self.title("Salón Spa Rodríguez — Sistema de Gestión Integral (MySQL 8.0)")
        self.geometry("1260x760")
        self.minsize(1080, 660)
        self.configure(bg=COLOR_BG)

        self._configurar_estilos()
        self.usuario_activo = self._determinar_usuario_inicial()
        self._construir_layout_base()
        self.mostrar_vista("usuarios")

    def _configurar_estilos(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Treeview", font=("Segoe UI", 9), rowheight=27, background="white", fieldbackground="white")
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=COLOR_PRIMARY,
            foreground="white",
            padding=(6, 5),
        )
        style.map("Treeview", background=[("selected", "#DBEAFE")], foreground=[("selected", "#1E3A8A")])
        style.configure("TCombobox", padding=4, font=("Segoe UI", 9))

    def _determinar_usuario_inicial(self) -> dict:
        usuarios = self.db.obtener_usuarios_detallados()
        if not usuarios:
            return {"id_usuario": 1, "nombre": "Administrador", "rol": "Administrador"}
        # Preferir al primer Administrador (Rosa Rodriguez)
        for u in usuarios:
            if u["rol"] == "Administrador":
                return u
        return usuarios[0]

    def _construir_layout_base(self) -> None:
        # Barra superior (Header)
        self.header = tk.Frame(self, bg="white", height=56, highlightthickness=1, highlightbackground="#E2E8F0")
        self.header.pack(side=tk.TOP, fill=tk.X)
        self.header.pack_propagate(False)

        tk.Label(
            self.header,
            text="SALÓN SPA RODRÍGUEZ — SISTEMA TRANSACCIONAL LOCAL (SHARE EVERYTHING)",
            font=("Segoe UI", 12, "bold"),
            fg=COLOR_SIDEBAR,
            bg="white",
        ).pack(side=tk.LEFT, padx=18)

        # Contenedor de usuario activo y selector de BD
        frame_db = tk.Frame(self.header, bg="white")
        frame_db.pack(side=tk.RIGHT, padx=16)

        # Badge de usuario autenticado
        self.frame_user_badge = tk.Frame(frame_db, bg="#EFF6FF", highlightthickness=1, highlightbackground="#BFDBFE", padx=8, pady=2)
        self.frame_user_badge.pack(side=tk.LEFT, padx=(0, 14))

        self.lbl_usuario_badge = tk.Label(
            self.frame_user_badge,
            text=f"👤 {self.usuario_activo.get('username', 'rosa.admin')} — {self.usuario_activo['nombre']} ({'🔑 Admin' if self.usuario_activo['rol'] == 'Administrador' else '🛠️ Trabajador'})",
            font=("Segoe UI", 9, "bold"),
            fg="#1E40AF",
            bg="#EFF6FF",
        )
        self.lbl_usuario_badge.pack(side=tk.LEFT, padx=(2, 6))

        tk.Button(
            self.frame_user_badge,
            text="🔐 Login / Cambiar",
            font=("Segoe UI", 8, "bold"),
            bg="#2563EB",
            fg="white",
            bd=0,
            padx=7,
            pady=2,
            cursor="hand2",
            command=lambda: self.mostrar_vista("login"),
        ).pack(side=tk.LEFT)

        tk.Label(frame_db, text="Base de Datos MySQL:", font=("Segoe UI", 9, "bold"), fg=COLOR_MUTED, bg="white").pack(
            side=tk.LEFT, padx=(0, 6)
        )
        bases = self.db.listar_bases_spa()
        self.var_bd = tk.StringVar(value=str(self.db.params.get("database", "spa_rodriguez")))
        self.combo_bd = ttk.Combobox(frame_db, textvariable=self.var_bd, values=bases, state="readonly", width=22)
        self.combo_bd.pack(side=tk.LEFT, padx=4)
        self.combo_bd.bind("<<ComboboxSelected>>", self._al_cambiar_bd)

        self.lbl_estado_conn = tk.Label(
            frame_db,
            text=f"● Conectado ({self.db.params['host']}:{self.db.params['port']})",
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_SUCCESS,
            bg="white",
        )
        self.lbl_estado_conn.pack(side=tk.LEFT, padx=(10, 0))

        # Contenedor principal (Sidebar + Área de trabajo)
        self.main_container = tk.Frame(self, bg=COLOR_BG)
        self.main_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Menú lateral (Sidebar)
        self.sidebar = tk.Frame(self.main_container, bg=COLOR_SIDEBAR, width=235)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        tk.Label(
            self.sidebar,
            text="MENÚ OPERATIVO",
            font=("Segoe UI", 9, "bold"),
            fg="#93C5FD",
            bg=COLOR_SIDEBAR,
            anchor="w",
        ).pack(fill=tk.X, padx=16, pady=(18, 8))

        self.botones_menu: dict[str, tk.Button] = {}
        opciones = [
            ("login", "🔐  Pestaña de Login"),
            ("usuarios", "👥  Usuarios (Admin / Trab.)"),
            ("dashboard", "📊  Panel Principal"),
            ("clientes", "🧑  Clientes y Preferencias"),
            ("citas", "📅  Agenda de Citas"),
            ("inventario", "📦  Stock, Ventas y Pedidos"),
            ("explorador", "🗄️  Explorador de Tablas SQL"),
        ]
        for clave, texto in opciones:
            btn = tk.Button(
                self.sidebar,
                text=texto,
                font=("Segoe UI", 10, "bold"),
                fg="white",
                bg=COLOR_SIDEBAR_BTN,
                activebackground=COLOR_SIDEBAR_ACT,
                activeforeground="white",
                bd=0,
                cursor="hand2",
                anchor="w",
                padx=16,
                pady=11,
                command=lambda k=clave: self.mostrar_vista(k),
            )
            btn.pack(fill=tk.X, padx=10, pady=3)
            self.botones_menu[clave] = btn

        # Pie del sidebar con información de la arquitectura
        frame_info = tk.Frame(self.sidebar, bg="#152C4E", padx=12, pady=10)
        frame_info.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=12)
        tk.Label(
            frame_info,
            text="Arquitectura Local:\n• Share Everything\n• MySQL 8.0 / InnoDB\n• Integridad Referencial",
            font=("Segoe UI", 8),
            fg="#CBD5E1",
            bg="#152C4E",
            justify=tk.LEFT,
        ).pack(anchor="w")

        # Área central dinámica
        self.content_area = tk.Frame(self.main_container, bg=COLOR_BG)
        self.content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=16, pady=14)
        self.vista_actual = "usuarios"

    def _al_cambiar_bd(self, _event=None) -> None:
        nueva_bd = self.var_bd.get()
        try:
            self.db.conectar(nueva_bd)
            self.usuario_activo = self._determinar_usuario_inicial()
            self._actualizar_badge_usuario()
            self.mostrar_vista(self.vista_actual)
        except Exception as exc:
            messagebox.showerror("Error al cambiar BD", f"No se pudo conectar a {nueva_bd}:\n{exc}")

    def _actualizar_badge_usuario(self) -> None:
        rol_txt = "🔑 Admin" if self.usuario_activo.get("rol") == "Administrador" else "🛠️ Trabajador"
        usr_txt = self.usuario_activo.get("username", "admin")
        self.lbl_usuario_badge.configure(text=f"👤 {usr_txt} — {self.usuario_activo['nombre']} ({rol_txt})")

    def _abrir_modal_login(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("Inicio de Sesión — Salón Spa Rodríguez")
        dlg.geometry("430x295")
        dlg.configure(bg="white")
        dlg.grab_set()

        tk.Label(dlg, text="AUTENTICACIÓN DE USUARIO", font=("Segoe UI", 11, "bold"), fg=COLOR_SIDEBAR, bg="white").pack(
            pady=(16, 4)
        )
        tk.Label(
            dlg,
            text="Ingrese o seleccione su User (username) y escriba su contraseña asignada:",
            font=("Segoe UI", 9),
            fg=COLOR_MUTED,
            bg="white",
            wraplength=390,
        ).pack(pady=(0, 12))

        usuarios = self.db.obtener_usuarios_detallados()
        opciones = [u.get("username", "") for u in usuarios]

        frame_form = tk.Frame(dlg, bg="white")
        frame_form.pack(fill=tk.X, padx=24)

        tk.Label(frame_form, text="User (Login) (*):", font=("Segoe UI", 9, "bold"), bg="white", fg=COLOR_TEXT).grid(
            row=0, column=0, sticky="w", pady=4
        )
        var_login_usr = tk.StringVar(value=opciones[0] if opciones else "")
        combo_usr = ttk.Combobox(frame_form, textvariable=var_login_usr, values=opciones, width=32)
        combo_usr.grid(row=0, column=1, pady=4, padx=6)

        tk.Label(frame_form, text="Contraseña (*):", font=("Segoe UI", 9, "bold"), bg="white", fg=COLOR_TEXT).grid(
            row=1, column=0, sticky="w", pady=6
        )
        var_login_pwd = tk.StringVar()
        ent_pwd = ttk.Entry(frame_form, textvariable=var_login_pwd, show="*", width=34)
        ent_pwd.grid(row=1, column=1, pady=6, padx=6)
        ent_pwd.focus_set()

        def verificar_acceso():
            ident = var_login_usr.get().strip()
            pwd = var_login_pwd.get().strip()
            u_obj = self.db.validar_login(ident, pwd)
            if u_obj:
                self.usuario_activo = u_obj
                self._actualizar_badge_usuario()
                dlg.destroy()
                messagebox.showinfo(
                    "Acceso Concedido",
                    f"Bienvenido(a) {u_obj['nombre']} (User: {u_obj['username']}) — Rol: {u_obj['rol']}.",
                )
            else:
                messagebox.showerror("Credenciales Inválidas", "El User o la contraseña ingresada no son válidos.", parent=dlg)

        ent_pwd.bind("<Return>", lambda _e: verificar_acceso())

        btn_entrar = tk.Button(
            dlg,
            text="🔓 Validar e Iniciar Sesión",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_SUCCESS,
            fg="white",
            bd=0,
            pady=8,
            cursor="hand2",
            command=verificar_acceso,
        )
        btn_entrar.pack(fill=tk.X, padx=24, pady=(16, 6))

    def limpiar_contenido(self) -> None:
        for widget in self.content_area.winfo_children():
            widget.destroy()

    def mostrar_vista(self, clave: str) -> None:
        self.vista_actual = clave
        for k, btn in self.botones_menu.items():
            btn.configure(bg=COLOR_SIDEBAR_ACT if k == clave else COLOR_SIDEBAR_BTN)

        self.limpiar_contenido()
        if clave == "login":
            self._vista_login()
        elif clave == "dashboard":
            self._vista_dashboard()
        elif clave == "usuarios":
            self._vista_usuarios()
        elif clave == "clientes":
            self._vista_clientes()
        elif clave == "citas":
            self._vista_citas()
        elif clave == "inventario":
            self._vista_inventario()
        elif clave == "explorador":
            self._vista_explorador()

    # ==========================================================================
    # VISTA 0: PESTAÑA DE LOGIN (AUTENTICACIÓN CON USER Y CONTRASEÑA)
    # ==========================================================================
    def _vista_login(self) -> None:
        top = tk.Frame(self.content_area, bg=COLOR_BG)
        top.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            top,
            text="Pestaña de Inicio de Sesión (Login por User y Contraseña)",
            font=("Segoe UI", 14, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        ).pack(side=tk.LEFT)

        split = tk.Frame(self.content_area, bg=COLOR_BG)
        split.pack(fill=tk.BOTH, expand=True)

        # Panel Izquierdo: Tarjeta de Login
        panel_login = tk.Frame(split, bg=COLOR_CARD, width=410, highlightthickness=1, highlightbackground="#CBD5E1", padx=24, pady=22)
        panel_login.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        panel_login.pack_propagate(False)

        tk.Label(
            panel_login,
            text="🔐 ACCESO AL SISTEMA",
            font=("Segoe UI", 13, "bold"),
            fg=COLOR_SIDEBAR,
            bg=COLOR_CARD,
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            panel_login,
            text="Ingrese su User asignado (ej. rosa.admin, lucia.spa) y su contraseña para autenticar su sesión activa en el Salón Spa Rodríguez.",
            font=("Segoe UI", 9),
            fg=COLOR_MUTED,
            bg=COLOR_CARD,
            wraplength=360,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 16))

        # Banner de sesión activa actual
        card_actual = tk.Frame(panel_login, bg="#EFF6FF", highlightthickness=1, highlightbackground="#BFDBFE", padx=12, pady=10)
        card_actual.pack(fill=tk.X, pady=(0, 18))

        tk.Label(card_actual, text="SESIÓN ACTIVA ACTUAL:", font=("Segoe UI", 8, "bold"), fg="#1E40AF", bg="#EFF6FF").pack(anchor="w")
        self.lbl_login_sesion_actual = tk.Label(
            card_actual,
            text=(
                f"• User: {self.usuario_activo.get('username', 'rosa.admin')}\n"
                f"• Nombre: {self.usuario_activo.get('nombre', '')}\n"
                f"• Rol: {self.usuario_activo.get('rol', '')} ({self.usuario_activo.get('especialidad_mostrar', '')})"
            ),
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_TEXT,
            bg="#EFF6FF",
            justify=tk.LEFT,
        )
        self.lbl_login_sesion_actual.pack(anchor="w", pady=(4, 0))

        usuarios = self.db.obtener_usuarios_detallados()
        lista_usernames = [u.get("username", "") for u in usuarios]

        tk.Label(panel_login, text="User (Usuario de Login) (*):", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT, bg=COLOR_CARD).pack(
            anchor="w", pady=(4, 2)
        )
        self.var_tab_login_user = tk.StringVar(value=self.usuario_activo.get("username", lista_usernames[0] if lista_usernames else ""))
        combo_login_usr = ttk.Combobox(panel_login, textvariable=self.var_tab_login_user, values=lista_usernames, font=("Segoe UI", 10))
        combo_login_usr.pack(fill=tk.X, pady=(0, 12))

        tk.Label(panel_login, text="Contraseña (*):", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT, bg=COLOR_CARD).pack(
            anchor="w", pady=(2, 2)
        )
        frame_pwd_login = tk.Frame(panel_login, bg=COLOR_CARD)
        frame_pwd_login.pack(fill=tk.X, pady=(0, 16))

        self.var_tab_login_pwd = tk.StringVar()
        ent_login_pwd = ttk.Entry(frame_pwd_login, textvariable=self.var_tab_login_pwd, font=("Segoe UI", 10), show="*")
        ent_login_pwd.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def toggle_pwd_login():
            if ent_login_pwd.cget("show") == "*":
                ent_login_pwd.configure(show="")
                btn_ver_pwd.configure(text="🙈 Ocultar")
            else:
                ent_login_pwd.configure(show="*")
                btn_ver_pwd.configure(text="👁️ Mostrar")

        btn_ver_pwd = tk.Button(frame_pwd_login, text="👁️ Mostrar", font=("Segoe UI", 8), bg="#E2E8F0", bd=0, padx=8, pady=4, command=toggle_pwd_login)
        btn_ver_pwd.pack(side=tk.LEFT, padx=(6, 0))

        self.lbl_login_feedback = tk.Label(panel_login, text="", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, wraplength=355, justify=tk.LEFT)
        self.lbl_login_feedback.pack(anchor="w", pady=(0, 8))

        def ejecutar_login_pestana():
            u_in = self.var_tab_login_user.get().strip()
            p_in = self.var_tab_login_pwd.get().strip()
            if not u_in or not p_in:
                self.lbl_login_feedback.configure(text="⚠️ Ingrese tanto el User como la Contraseña.", fg=COLOR_WARNING)
                return
            u_valido = self.db.validar_login(u_in, p_in)
            if u_valido:
                self.usuario_activo = u_valido
                self._actualizar_badge_usuario()
                self.lbl_login_sesion_actual.configure(
                    text=(
                        f"• User: {u_valido.get('username', '')}\n"
                        f"• Nombre: {u_valido.get('nombre', '')}\n"
                        f"• Rol: {u_valido.get('rol', '')} ({u_valido.get('especialidad_mostrar', '')})"
                    )
                )
                self.lbl_login_feedback.configure(
                    text=f"✅ ¡Sesión iniciada correctamente como '{u_valido['username']}' ({u_valido['rol']})!",
                    fg=COLOR_SUCCESS,
                )
                messagebox.showinfo(
                    "Inicio de Sesión Exitoso",
                    f"Bienvenido(a) {u_valido['nombre']}\n\n• User: {u_valido['username']}\n• Rol en el sistema: {u_valido['rol']}\n• Área: {u_valido['especialidad_mostrar']}",
                )
            else:
                self.lbl_login_feedback.configure(
                    text="❌ User o contraseña incorrectos. Verifique en la tabla de credenciales a la derecha.",
                    fg=COLOR_DANGER,
                )

        ent_login_pwd.bind("<Return>", lambda _e: ejecutar_login_pestana())

        tk.Button(
            panel_login,
            text="🔓  Iniciar Sesión con este User",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_SUCCESS,
            fg="white",
            bd=0,
            pady=10,
            cursor="hand2",
            command=ejecutar_login_pestana,
        ).pack(fill=tk.X, pady=(4, 8))

        tk.Button(
            panel_login,
            text="👥  Ir a Gestión de Usuarios (Crear / Editar User)",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_PRIMARY,
            fg="white",
            bd=0,
            pady=8,
            cursor="hand2",
            command=lambda: self.mostrar_vista("usuarios"),
        ).pack(fill=tk.X)

        # Panel Derecho: Directorio de Credenciales (Users y Contraseñas para demostración)
        panel_dir = tk.Frame(split, bg=COLOR_CARD, highlightthickness=1, highlightbackground="#CBD5E1", padx=16, pady=16)
        panel_dir.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            panel_dir,
            text="Directorio de Cuentas de Usuario (Haga clic en un usuario para cargar su User)",
            font=("Segoe UI", 11, "bold"),
            fg=COLOR_SIDEBAR,
            bg=COLOR_CARD,
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            panel_dir,
            text="Seleccione cualquier fila de la tabla para autocompletar el User y probar el inicio de sesión como Administrador o Trabajador.",
            font=("Segoe UI", 9),
            fg=COLOR_MUTED,
            bg=COLOR_CARD,
        ).pack(anchor="w", pady=(0, 10))

        cols_dir = ("id_usuario", "username", "nombre", "rol", "especialidad", "contrasena")
        tree_dir = ttk.Treeview(panel_dir, columns=cols_dir, show="headings", height=12, selectmode="browse")
        for cid, tit, anc, al in [
            ("id_usuario", "ID", 45, tk.CENTER),
            ("username", "User (Login) 👤", 125, tk.CENTER),
            ("nombre", "Nombre Completo", 185, tk.W),
            ("rol", "Rol en Sistema", 110, tk.CENTER),
            ("especialidad", "Especialidad / Área", 155, tk.W),
            ("contrasena", "Contraseña 🔑", 105, tk.CENTER),
        ]:
            tree_dir.heading(cid, text=tit)
            tree_dir.column(cid, width=anc, anchor=al)

        tree_dir.tag_configure("admin_row", background="#FEF3C7")
        tree_dir.tag_configure("trab_row", background="#ECFDF5")
        tree_dir.pack(fill=tk.BOTH, expand=True)

        for u in usuarios:
            tag = "trab_row" if u["rol"] == "Trabajador" else "admin_row"
            tree_dir.insert(
                "",
                tk.END,
                iid=str(u["id_usuario"]),
                values=(
                    u["id_usuario"],
                    u.get("username", ""),
                    u["nombre"],
                    f"🛠️ {u['rol']}" if u["rol"] == "Trabajador" else f"🔑 {u['rol']}",
                    u["especialidad_mostrar"],
                    u.get("contrasena", "spa123"),
                ),
                tags=(tag,),
            )

        def al_seleccionar_cuenta_login(_ev=None):
            sel = tree_dir.selection()
            if not sel:
                return
            uid = int(sel[0])
            u_sel = next((x for x in usuarios if x["id_usuario"] == uid), None)
            if u_sel:
                self.var_tab_login_user.set(u_sel.get("username", ""))
                self.var_tab_login_pwd.set(u_sel.get("contrasena", ""))
                self.lbl_login_feedback.configure(
                    text=f"ℹ️ User '{u_sel.get('username')}' cargado. Presione 'Iniciar Sesión con este User'.",
                    fg=COLOR_PRIMARY,
                )

        tree_dir.bind("<<TreeviewSelect>>", al_seleccionar_cuenta_login)

    # ==========================================================================
    # VISTA 1: GESTIÓN DE USUARIOS (ADMINISTRADOR / TRABAJADOR)
    # ==========================================================================
    def _vista_usuarios(self) -> None:
        # Encabezado de sección
        top = tk.Frame(self.content_area, bg=COLOR_BG)
        top.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            top,
            text="Gestión de Usuarios del Sistema (Administradores y Trabajadores)",
            font=("Segoe UI", 14, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        ).pack(side=tk.LEFT)

        if "usuario" not in self.db.tablas_disponibles:
            tk.Label(
                self.content_area,
                text="La base de datos seleccionada no contiene la tabla 'usuario'. Seleccione 'spa_rodriguez' o 'spa_rodriguez_pruebas' en la barra superior.",
                font=("Segoe UI", 11),
                fg=COLOR_DANGER,
                bg=COLOR_BG,
            ).pack(pady=40)
            return

        # Contenedor dividido: Izquierda (Tabla y Filtros) / Derecha (Formulario Agregar/Editar/Quitar)
        split = tk.Frame(self.content_area, bg=COLOR_BG)
        split.pack(fill=tk.BOTH, expand=True)

        panel_izq = tk.Frame(split, bg=COLOR_CARD, highlightthickness=1, highlightbackground="#CBD5E1", padx=14, pady=12)
        panel_izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        panel_der = tk.Frame(split, bg=COLOR_CARD, width=355, highlightthickness=1, highlightbackground="#CBD5E1", padx=16, pady=14)
        panel_der.pack(side=tk.RIGHT, fill=tk.Y)
        panel_der.pack_propagate(False)

        # --- Barra de filtros en panel izquierdo ---
        bar_filtro = tk.Frame(panel_izq, bg=COLOR_CARD)
        bar_filtro.pack(fill=tk.X, pady=(0, 10))

        tk.Label(bar_filtro, text="Filtrar Rol:", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT).pack(
            side=tk.LEFT
        )
        self.var_filtro_rol = tk.StringVar(value="TODOS")
        for valor, etiqueta in [("TODOS", "Todos"), ("ADMINISTRADOR", "Administradores"), ("TRABAJADOR", "Trabajadores")]:
            rb = tk.Radiobutton(
                bar_filtro,
                text=etiqueta,
                variable=self.var_filtro_rol,
                value=valor,
                bg=COLOR_CARD,
                font=("Segoe UI", 9),
                command=self._refrescar_tabla_usuarios,
            )
            rb.pack(side=tk.LEFT, padx=4)

        tk.Label(bar_filtro, text="   Buscar:", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT).pack(
            side=tk.LEFT
        )
        self.var_buscar_usr = tk.StringVar()
        self.var_buscar_usr.trace_add("write", lambda *_: self._refrescar_tabla_usuarios())
        ent_buscar = ttk.Entry(bar_filtro, textvariable=self.var_buscar_usr, width=22)
        ent_buscar.pack(side=tk.LEFT, padx=6)

        # Resumen de conteo rápido
        self.lbl_resumen_usuarios = tk.Label(
            panel_izq,
            text="",
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_PRIMARY,
            bg="#EFF6FF",
            padx=10,
            pady=5,
            anchor="w",
        )
        self.lbl_resumen_usuarios.pack(fill=tk.X, pady=(0, 8))

        # Tabla Treeview de usuarios
        cols = ("id_usuario", "username", "nombre", "telefono", "rol", "especialidad", "contrasena", "almacen", "actividad")
        frame_tree = tk.Frame(panel_izq, bg=COLOR_CARD)
        frame_tree.pack(fill=tk.BOTH, expand=True)

        scroll_y = ttk.Scrollbar(frame_tree, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_usuarios = ttk.Treeview(
            frame_tree, columns=cols, show="headings", yscrollcommand=scroll_y.set, selectmode="browse"
        )
        scroll_y.config(command=self.tree_usuarios.yview)

        definiciones = [
            ("id_usuario", "ID", 40, tk.CENTER),
            ("username", "User (Login) 👤", 105, tk.CENTER),
            ("nombre", "Nombre Completo", 155, tk.W),
            ("telefono", "Teléfono", 75, tk.CENTER),
            ("rol", "Rol en Sistema", 95, tk.CENTER),
            ("especialidad", "Especialidad / Área", 135, tk.W),
            ("contrasena", "Contraseña 🔑", 90, tk.CENTER),
            ("almacen", "Almacén", 70, tk.CENTER),
            ("actividad", "Cli / Cit / Ped", 100, tk.CENTER),
        ]
        for col_id, titulo, ancho, align in definiciones:
            self.tree_usuarios.heading(col_id, text=titulo)
            self.tree_usuarios.column(col_id, width=ancho, anchor=align)

        self.tree_usuarios.tag_configure("admin_row", background="#FEF3C7")
        self.tree_usuarios.tag_configure("trab_row", background="#ECFDF5")
        self.tree_usuarios.pack(fill=tk.BOTH, expand=True)
        self.tree_usuarios.bind("<<TreeviewSelect>>", self._al_seleccionar_usuario)

        # Botonera inferior de la tabla
        bar_acciones_tabla = tk.Frame(panel_izq, bg=COLOR_CARD)
        bar_acciones_tabla.pack(fill=tk.X, pady=(10, 0))

        tk.Button(
            bar_acciones_tabla,
            text="➕ Limpiar Formulario (Nuevo Usuario)",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_PRIMARY,
            fg="white",
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            command=self._limpiar_formulario_usuario,
        ).pack(side=tk.LEFT)

        tk.Button(
            bar_acciones_tabla,
            text="🗑️ Quitar / Eliminar Usuario Seleccionado",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_DANGER,
            fg="white",
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            command=self._accion_eliminar_usuario,
        ).pack(side=tk.RIGHT)

        # --- Panel derecho: Formulario de Agregar / Editar Usuario ---
        self.lbl_titulo_form_usr = tk.Label(
            panel_der,
            text="AGREGAR NUEVO USUARIO",
            font=("Segoe UI", 11, "bold"),
            fg=COLOR_SIDEBAR,
            bg=COLOR_CARD,
        )
        self.lbl_titulo_form_usr.pack(anchor="w", pady=(0, 4))

        tk.Label(
            panel_der,
            text="Complete los datos para registrar un Administrador o un Trabajador en la base de datos.",
            font=("Segoe UI", 9),
            fg=COLOR_MUTED,
            bg=COLOR_CARD,
            wraplength=315,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 10))

        self.id_usuario_editando: int | None = None

        # Campo Nombre
        tk.Label(panel_der, text="Nombre y Apellidos (*):", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT).pack(
            anchor="w", pady=(2, 2)
        )
        self.var_usr_nombre = tk.StringVar()
        ttk.Entry(panel_der, textvariable=self.var_usr_nombre, font=("Segoe UI", 10)).pack(fill=tk.X, pady=(0, 6))

        # Campo User (username para Login)
        tk.Label(panel_der, text="User de Login (username) (*):", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT).pack(
            anchor="w", pady=(2, 2)
        )
        frame_uname = tk.Frame(panel_der, bg=COLOR_CARD)
        frame_uname.pack(fill=tk.X, pady=(0, 6))

        self.var_usr_username = tk.StringVar()
        ttk.Entry(frame_uname, textvariable=self.var_usr_username, font=("Segoe UI", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True)

        def sugerir_username():
            nom = self.var_usr_nombre.get().strip() or "usuario"
            rol = self.var_usr_rol.get()
            self.var_usr_username.set(self.db.generar_username_sugerido(nom, rol))

        tk.Button(frame_uname, text="🎲 Sugerir User", font=("Segoe UI", 8), bg="#E2E8F0", bd=0, padx=6, pady=2, command=sugerir_username).pack(
            side=tk.LEFT, padx=(4, 0)
        )

        # Campo Teléfono
        tk.Label(
            panel_der, text="Teléfono Celular (9 dígitos):", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT
        ).pack(anchor="w", pady=(2, 2))
        self.var_usr_telefono = tk.StringVar()
        ttk.Entry(panel_der, textvariable=self.var_usr_telefono, font=("Segoe UI", 10)).pack(fill=tk.X, pady=(0, 6))

        # Campo Contraseña
        tk.Label(
            panel_der, text="Contraseña de Acceso (*):", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT
        ).pack(anchor="w", pady=(2, 2))
        frame_pwd = tk.Frame(panel_der, bg=COLOR_CARD)
        frame_pwd.pack(fill=tk.X, pady=(0, 8))

        self.var_usr_password = tk.StringVar(value="spa123")
        self.ent_usr_password = ttk.Entry(frame_pwd, textvariable=self.var_usr_password, font=("Segoe UI", 10), show="")
        self.ent_usr_password.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def alternar_ver_clave():
            if self.ent_usr_password.cget("show") == "":
                self.ent_usr_password.configure(show="*")
                btn_ojo.configure(text="👁️ Ver")
            else:
                self.ent_usr_password.configure(show="")
                btn_ojo.configure(text="🙈 Ocultar")

        def sugerir_clave():
            rol_actual = self.var_usr_rol.get()
            nom_actual = self.var_usr_nombre.get().strip().split()[0].lower() if self.var_usr_nombre.get().strip() else "spa"
            sug = f"{nom_actual}2026" if rol_actual == "Trabajador" else f"admin_{nom_actual}"
            self.var_usr_password.set(sug)

        btn_ojo = tk.Button(frame_pwd, text="🙈 Ocultar", font=("Segoe UI", 8), bg="#E2E8F0", bd=0, padx=5, pady=2, command=alternar_ver_clave)
        btn_ojo.pack(side=tk.LEFT, padx=3)

        btn_sug = tk.Button(frame_pwd, text="🎲 Sugerir", font=("Segoe UI", 8), bg="#E2E8F0", bd=0, padx=5, pady=2, command=sugerir_clave)
        btn_sug.pack(side=tk.LEFT)

        # Selección de Rol: Administrador vs Trabajador
        tk.Label(
            panel_der,
            text="Tipo / Rol de Usuario (*):",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        ).pack(anchor="w", pady=(2, 4))

        frame_roles = tk.Frame(panel_der, bg="#F8FAFC", highlightthickness=1, highlightbackground="#CBD5E1", padx=10, pady=8)
        frame_roles.pack(fill=tk.X, pady=(0, 10))

        self.var_usr_rol = tk.StringVar(value="Trabajador")
        rb_admin = tk.Radiobutton(
            frame_roles,
            text="🔑 Administrador (Gestión / Recepción / Almacén)",
            variable=self.var_usr_rol,
            value="Administrador",
            font=("Segoe UI", 9, "bold"),
            bg="#F8FAFC",
            fg="#92400E",
            command=self._actualizar_estado_campos_rol,
        )
        rb_admin.pack(anchor="w", pady=2)

        rb_trab = tk.Radiobutton(
            frame_roles,
            text="🛠️ Trabajador / Empleado (Especialista Spa)",
            variable=self.var_usr_rol,
            value="Trabajador",
            font=("Segoe UI", 9, "bold"),
            bg="#F8FAFC",
            fg="#065F46",
            command=self._actualizar_estado_campos_rol,
        )
        rb_trab.pack(anchor="w", pady=2)

        # Especialidad (activa cuando es Trabajador)
        self.lbl_especialidad = tk.Label(
            panel_der,
            text="Especialidad del Trabajador (*):",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        )
        self.lbl_especialidad.pack(anchor="w", pady=(4, 2))

        self.var_usr_especialidad = tk.StringVar()
        especialidades = self.db.listar_especialidades()
        self.combo_usr_especialidad = ttk.Combobox(
            panel_der, textvariable=self.var_usr_especialidad, values=especialidades, font=("Segoe UI", 9)
        )
        if especialidades:
            self.combo_usr_especialidad.current(0)
        self.combo_usr_especialidad.pack(fill=tk.X, pady=(0, 10))

        # Opción adicional para Administrador: asignar un nuevo almacén
        self.var_usr_almacen = tk.BooleanVar(value=False)
        self.chk_almacen = tk.Checkbutton(
            panel_der,
            text="Registrar también como responsable de Almacén",
            variable=self.var_usr_almacen,
            bg=COLOR_CARD,
            font=("Segoe UI", 9),
        )
        self.chk_almacen.pack(anchor="w", pady=(0, 12))

        # Botón Guardar (Agregar o Actualizar)
        self.btn_guardar_usr = tk.Button(
            panel_der,
            text="💾  Guardar Nuevo Usuario",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_SUCCESS,
            fg="white",
            bd=0,
            pady=10,
            cursor="hand2",
            command=self._accion_guardar_usuario,
        )
        self.btn_guardar_usr.pack(fill=tk.X, pady=(4, 6))

        # Botón Quitar desde el formulario
        self.btn_quitar_form = tk.Button(
            panel_der,
            text="🗑️  Quitar Usuario Seleccionado",
            font=("Segoe UI", 9, "bold"),
            bg="#FEE2E2",
            fg=COLOR_DANGER,
            bd=0,
            pady=8,
            cursor="hand2",
            command=self._accion_eliminar_usuario,
        )
        self.btn_quitar_form.pack(fill=tk.X, pady=(2, 6))

        # Nota explicativa de cómo se guarda en el modelo relacional
        nota_bd = tk.Label(
            panel_der,
            text="Nota del Modelo Relacional:\n• Administrador: se registra en la tabla USUARIO.\n• Trabajador: se registra en USUARIO y se vincula automáticamente en EMPLEADO con su especialidad.",
            font=("Segoe UI", 8),
            fg=COLOR_MUTED,
            bg="#F1F5F9",
            padx=8,
            pady=8,
            justify=tk.LEFT,
            wraplength=310,
        )
        nota_bd.pack(side=tk.BOTTOM, fill=tk.X)

        self._actualizar_estado_campos_rol()
        self._refrescar_tabla_usuarios()

    def _actualizar_estado_campos_rol(self) -> None:
        rol = self.var_usr_rol.get()
        if rol == "Trabajador":
            self.combo_usr_especialidad.configure(state="normal")
            self.lbl_especialidad.configure(fg=COLOR_TEXT)
        else:
            self.combo_usr_especialidad.configure(state="disabled")
            self.lbl_especialidad.configure(fg=COLOR_MUTED)

    def _refrescar_tabla_usuarios(self) -> None:
        if not hasattr(self, "tree_usuarios"):
            return
        for item in self.tree_usuarios.get_children():
            self.tree_usuarios.delete(item)

        usuarios = self.db.obtener_usuarios_detallados(
            filtro_rol=self.var_filtro_rol.get(),
            busqueda=self.var_buscar_usr.get(),
        )
        todos = self.db.obtener_usuarios_detallados()
        n_admin = sum(1 for u in todos if u["rol"] == "Administrador")
        n_trab = sum(1 for u in todos if u["rol"] == "Trabajador")
        self.lbl_resumen_usuarios.configure(
            text=f"Total Usuarios en BD: {len(todos)}   |   🔑 Administradores: {n_admin}   |   🛠️ Trabajadores (Empleados): {n_trab}"
        )

        for u in usuarios:
            tag = "trab_row" if u["rol"] == "Trabajador" else "admin_row"
            act = f"{u['total_clientes']} cli / {u['total_citas']} cit / {u['total_pedidos']} ped"
            self.tree_usuarios.insert(
                "",
                tk.END,
                iid=str(u["id_usuario"]),
                values=(
                    u["id_usuario"],
                    f"👤 {u.get('username', '')}",
                    u["nombre"],
                    u["telefono"] or "—",
                    f"🛠️ {u['rol']}" if u["rol"] == "Trabajador" else f"🔑 {u['rol']}",
                    u["especialidad_mostrar"],
                    f"🔑 {u.get('contrasena', 'spa123')}",
                    u["almacenes_mostrar"],
                    act,
                ),
                tags=(tag,),
            )

    def _al_seleccionar_usuario(self, _event=None) -> None:
        sel = self.tree_usuarios.selection()
        if not sel:
            return
        id_usr = int(sel[0])
        todos = self.db.obtener_usuarios_detallados()
        datos = next((u for u in todos if u["id_usuario"] == id_usr), None)
        if not datos:
            return

        self.id_usuario_editando = id_usr
        self.lbl_titulo_form_usr.configure(text=f"EDITAR USUARIO #{id_usr}", fg=COLOR_PRIMARY)
        self.btn_guardar_usr.configure(text=f"💾  Actualizar Usuario #{id_usr}", bg=COLOR_PRIMARY)

        self.var_usr_nombre.set(datos["nombre"])
        self.var_usr_username.set(datos.get("username", ""))
        self.var_usr_telefono.set(datos["telefono"] or "")
        self.var_usr_password.set(datos.get("contrasena", "spa123"))
        self.var_usr_rol.set(datos["rol"])
        if datos.get("especialidad"):
            self.var_usr_especialidad.set(datos["especialidad"].split(",")[0].strip())
        self.var_usr_almacen.set(False)
        self.chk_almacen.configure(state="disabled")
        self._actualizar_estado_campos_rol()

    def _limpiar_formulario_usuario(self) -> None:
        self.id_usuario_editando = None
        self.tree_usuarios.selection_remove(self.tree_usuarios.selection())
        self.lbl_titulo_form_usr.configure(text="AGREGAR NUEVO USUARIO", fg=COLOR_SIDEBAR)
        self.btn_guardar_usr.configure(text="💾  Guardar Nuevo Usuario", bg=COLOR_SUCCESS)
        self.var_usr_nombre.set("")
        self.var_usr_username.set("")
        self.var_usr_telefono.set("")
        self.var_usr_password.set("spa123")
        self.var_usr_rol.set("Trabajador")
        especialidades = self.db.listar_especialidades()
        self.combo_usr_especialidad.configure(values=especialidades)
        if especialidades:
            self.var_usr_especialidad.set(especialidades[0])
        self.var_usr_almacen.set(False)
        self.chk_almacen.configure(state="normal")
        self._actualizar_estado_campos_rol()

    def _accion_guardar_usuario(self) -> None:
        nombre = self.var_usr_nombre.get()
        username = self.var_usr_username.get()
        telefono = self.var_usr_telefono.get()
        contrasena = self.var_usr_password.get()
        rol = self.var_usr_rol.get()
        especialidad = self.var_usr_especialidad.get()

        try:
            if self.id_usuario_editando is None:
                nuevo_id = self.db.agregar_usuario(
                    nombre=nombre,
                    telefono=telefono,
                    rol=rol,
                    especialidad=especialidad,
                    registrar_almacen=self.var_usr_almacen.get(),
                    contrasena=contrasena,
                    username=username,
                )
                messagebox.showinfo(
                    "Usuario Registrado",
                    f"Se agregó correctamente a '{nombre.strip()}' (ID #{nuevo_id}) con el User '{username.strip() or self.db.generar_username_sugerido(nombre, rol)}', rol de {rol} y contraseña asignada.",
                )
            else:
                self.db.actualizar_usuario(
                    id_usuario=self.id_usuario_editando,
                    nombre=nombre,
                    telefono=telefono,
                    rol=rol,
                    especialidad=especialidad,
                    contrasena=contrasena,
                    username=username,
                )
                messagebox.showinfo(
                    "Usuario Actualizado",
                    f"Se actualizaron los datos, User y rol ({rol}) del usuario #{self.id_usuario_editando}.",
                )
            self._limpiar_formulario_usuario()
            self._refrescar_tabla_usuarios()
        except Exception as exc:
            messagebox.showerror("Validación / Error SQL", str(exc))

    def _accion_eliminar_usuario(self) -> None:
        sel = self.tree_usuarios.selection()
        if not sel and self.id_usuario_editando is None:
            messagebox.showwarning("Selección requerida", "Seleccione un usuario de la tabla para poder quitarlo.")
            return

        id_usr = int(sel[0]) if sel else int(self.id_usuario_editando)
        todos = self.db.obtener_usuarios_detallados()
        datos = next((u for u in todos if u["id_usuario"] == id_usr), None)
        if not datos:
            return

        deps = self.db.obtener_dependencias_usuario(id_usr)
        if not deps:
            confirmar = messagebox.askyesno(
                "Confirmar Eliminación",
                f"¿Está seguro de quitar al usuario #{id_usr} '{datos['nombre']}' ({datos['rol']}) de la base de datos?",
            )
            if not confirmar:
                return
            try:
                self.db.eliminar_usuario(id_usr)
                messagebox.showinfo("Usuario Eliminado", f"El usuario '{datos['nombre']}' fue eliminado correctamente.")
                self._limpiar_formulario_usuario()
                self._refrescar_tabla_usuarios()
            except Exception as exc:
                messagebox.showerror("Error al eliminar", str(exc))
            return

        # Si tiene registros históricos asociados (ON DELETE RESTRICT), ofrecer diálogo de reasignación
        otros = [u for u in todos if u["id_usuario"] != id_usr]
        if not otros:
            messagebox.showerror(
                "No se puede eliminar",
                "Este es el único usuario en el sistema y tiene registros históricos vinculados.",
            )
            return

        self._mostrar_dialogo_reasignar_y_eliminar(datos, deps, otros)

    def _mostrar_dialogo_reasignar_y_eliminar(self, datos: dict, deps: dict[str, int], otros: list[dict]) -> None:
        dlg = tk.Toplevel(self)
        dlg.title(f"Quitar Usuario #{datos['id_usuario']} con Historial")
        dlg.geometry("460x310")
        dlg.configure(bg="white")
        dlg.grab_set()

        resumen_deps = ", ".join(f"{v} en {k}" for k, v in deps.items())
        tk.Label(
            dlg,
            text=f"El usuario '{datos['nombre']}' ({datos['rol']}) tiene registros asociados:\n({resumen_deps})",
            font=("Segoe UI", 10, "bold"),
            fg=COLOR_TEXT,
            bg="white",
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=18, pady=(16, 8))

        tk.Label(
            dlg,
            text="Por integridad referencial (ON DELETE RESTRICT), seleccione a qué usuario activo desea reasignar esos registros antes de quitarlo:",
            font=("Segoe UI", 9),
            fg=COLOR_MUTED,
            bg="white",
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=18, pady=(0, 8))

        opciones = [f"{u['id_usuario']} — {u['nombre']} ({u['rol']})" for u in otros]
        var_dest = tk.StringVar(value=opciones[0])
        combo = ttk.Combobox(dlg, textvariable=var_dest, values=opciones, state="readonly", width=45)
        combo.pack(padx=18, pady=6)

        def confirmar_borrado():
            id_destino = int(var_dest.get().split("—")[0].strip())
            try:
                self.db.eliminar_usuario(datos["id_usuario"], id_usuario_reasignar=id_destino)
                dlg.destroy()
                messagebox.showinfo(
                    "Usuario Quitado",
                    f"Se reasignaron las referencias al usuario #{id_destino} y se eliminó a '{datos['nombre']}'.",
                )
                self._limpiar_formulario_usuario()
                self._refrescar_tabla_usuarios()
            except Exception as exc:
                messagebox.showerror("Error SQL", str(exc))

        frame_btns = tk.Frame(dlg, bg="white")
        frame_btns.pack(fill=tk.X, padx=18, pady=18)

        tk.Button(
            frame_btns,
            text="🗑️ Reasignar Historial y Quitar Usuario",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_DANGER,
            fg="white",
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2",
            command=confirmar_borrado,
        ).pack(side=tk.LEFT)

        tk.Button(
            frame_btns,
            text="Cancelar",
            font=("Segoe UI", 9),
            bg="#E2E8F0",
            fg=COLOR_TEXT,
            bd=0,
            padx=12,
            pady=8,
            command=dlg.destroy,
        ).pack(side=tk.RIGHT)

    # ==========================================================================
    # VISTA 2: PANEL PRINCIPAL (DASHBOARD EJECUTIVO)
    # ==========================================================================
    def _vista_dashboard(self) -> None:
        tk.Label(
            self.content_area,
            text="Panel Principal — Indicadores en Tiempo Real del Salón Spa Rodríguez",
            font=("Segoe UI", 14, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        ).pack(anchor="w", pady=(0, 12))

        # Tarjetas KPI
        frame_kpis = tk.Frame(self.content_area, bg=COLOR_BG)
        frame_kpis.pack(fill=tk.X, pady=(0, 14))

        usuarios = self.db.obtener_usuarios_detallados()
        n_admin = sum(1 for u in usuarios if u["rol"] == "Administrador")
        n_trab = sum(1 for u in usuarios if u["rol"] == "Trabajador")

        n_clientes = self.db.consultar("SELECT COUNT(*) AS n FROM cliente")[0]["n"] if "cliente" in self.db.tablas_disponibles else 0
        n_citas = self.db.consultar("SELECT COUNT(*) AS n FROM cita")[0]["n"] if "cita" in self.db.tablas_disponibles else 0
        stock_total = (
            self.db.consultar("SELECT COALESCE(SUM(stock), 0) AS s FROM producto")[0]["s"]
            if "producto" in self.db.tablas_disponibles
            else 0
        )
        ingresos_ventas = (
            self.db.consultar("SELECT COALESCE(SUM(total), 0) AS t FROM venta")[0]["t"]
            if "venta" in self.db.tablas_disponibles
            else Decimal("0.00")
        )

        tarjetas = [
            ("USUARIOS Y PERSONAL", f"{len(usuarios)} activos", f"🔑 {n_admin} Admin  |  🛠️ {n_trab} Trabajadores", "#1D4ED8"),
            ("CLIENTES REGISTRADOS", f"{n_clientes} clientes", "Atendidos con historial y preferencias", "#047857"),
            ("RESERVAS Y CITAS", f"{n_citas} citas", "Ciclo de vida controlado (RN-04)", "#B45309"),
            ("STOCK DE PRODUCTOS", f"{stock_total} botellas", "Unidades completas en almacén", "#6D28D9"),
            ("INGRESOS POR VENTAS", f"S/ {float(ingresos_ventas):.2f}", "Acumulado en comprobantes de venta", "#BE123C"),
        ]

        for titulo, valor, sub, color in tarjetas:
            card = tk.Frame(frame_kpis, bg="white", highlightthickness=1, highlightbackground="#CBD5E1", padx=14, pady=12)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
            tk.Frame(card, bg=color, height=4).pack(fill=tk.X, pady=(0, 6))
            tk.Label(card, text=titulo, font=("Segoe UI", 9, "bold"), fg=COLOR_MUTED, bg="white").pack(anchor="w")
            tk.Label(card, text=valor, font=("Segoe UI", 16, "bold"), fg=color, bg="white").pack(anchor="w", pady=3)
            tk.Label(card, text=sub, font=("Segoe UI", 8), fg=COLOR_TEXT, bg="white").pack(anchor="w")

        # Dos tablas inferiores: Estado de Citas y Productos con Menor Stock
        bottom = tk.Frame(self.content_area, bg=COLOR_BG)
        bottom.pack(fill=tk.BOTH, expand=True)

        p1 = tk.Frame(bottom, bg="white", highlightthickness=1, highlightbackground="#CBD5E1", padx=12, pady=12)
        p1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        tk.Label(p1, text="Resumen de Citas por Estado (RN-04)", font=("Segoe UI", 11, "bold"), bg="white", fg=COLOR_SIDEBAR).pack(
            anchor="w", pady=(0, 8)
        )
        t_est = ttk.Treeview(p1, columns=("estado", "cantidad"), show="headings", height=7)
        t_est.heading("estado", text="Estado de la Cita")
        t_est.heading("cantidad", text="Cantidad de Reservas")
        t_est.column("estado", width=180)
        t_est.column("cantidad", width=130, anchor=tk.CENTER)
        t_est.pack(fill=tk.BOTH, expand=True)

        if "estado_cita" in self.db.tablas_disponibles and "cita" in self.db.tablas_disponibles:
            filas_est = self.db.consultar(
                """
                SELECT e.descripcion AS estado, COUNT(c.numero_registro) AS cantidad
                FROM estado_cita e
                LEFT JOIN cita c ON c.id_estado = e.id_estado
                GROUP BY e.id_estado, e.descripcion
                ORDER BY e.id_estado
                """
            )
            for r in filas_est:
                t_est.insert("", tk.END, values=(r["estado"], r["cantidad"]))

        p2 = tk.Frame(bottom, bg="white", highlightthickness=1, highlightbackground="#CBD5E1", padx=12, pady=12)
        p2.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))
        tk.Label(p2, text="Control de Existencias — Productos con Menor Stock (RN-07 / RN-08)", font=("Segoe UI", 11, "bold"), bg="white", fg=COLOR_SIDEBAR).pack(
            anchor="w", pady=(0, 8)
        )
        t_prod = ttk.Treeview(p2, columns=("cod", "nombre", "precio", "stock"), show="headings", height=7)
        for cid, txt, w, al in [
            ("cod", "Código", 65, tk.CENTER),
            ("nombre", "Producto", 220, tk.W),
            ("precio", "Precio (S/)", 90, tk.E),
            ("stock", "Stock (Botellas)", 110, tk.CENTER),
        ]:
            t_prod.heading(cid, text=txt)
            t_prod.column(cid, width=w, anchor=al)
        t_prod.pack(fill=tk.BOTH, expand=True)

        if "producto" in self.db.tablas_disponibles and "codigo_producto" in self.db.columnas_por_tabla.get("producto", []):
            filas_p = self.db.consultar(
                "SELECT codigo_producto, nombre, precio_unitario, stock FROM producto ORDER BY stock ASC LIMIT 8"
            )
            for r in filas_p:
                t_prod.insert("", tk.END, values=(r["codigo_producto"], r["nombre"], f"{float(r['precio_unitario']):.2f}", r["stock"]))

    # ==========================================================================
    # VISTA 3: GESTIÓN DE CLIENTES Y PREFERENCIAS
    # ==========================================================================
    def _vista_clientes(self) -> None:
        tk.Label(
            self.content_area,
            text="Gestión de Clientes y Preferencias de Atención",
            font=("Segoe UI", 14, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        ).pack(anchor="w", pady=(0, 10))

        split = tk.Frame(self.content_area, bg=COLOR_BG)
        split.pack(fill=tk.BOTH, expand=True)

        izq = tk.Frame(split, bg="white", highlightthickness=1, highlightbackground="#CBD5E1", padx=14, pady=12)
        izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        der = tk.Frame(split, bg="white", width=340, highlightthickness=1, highlightbackground="#CBD5E1", padx=16, pady=14)
        der.pack(side=tk.RIGHT, fill=tk.Y)
        der.pack_propagate(False)

        cols = ("id", "cliente", "ciudad", "direccion", "atendido_por", "preferencias")
        self.tree_clientes = ttk.Treeview(izq, columns=cols, show="headings")
        for cid, txt, w in [
            ("id", "Código", 55),
            ("cliente", "Cliente", 175),
            ("ciudad", "Distrito / Ciudad", 120),
            ("direccion", "Dirección", 155),
            ("atendido_por", "Atendido por (Usuario)", 150),
            ("preferencias", "Preferencias", 180),
        ]:
            self.tree_clientes.heading(cid, text=txt)
            self.tree_clientes.column(cid, width=w)
        self.tree_clientes.pack(fill=tk.BOTH, expand=True)

        tk.Button(
            izq,
            text="🗑️ Eliminar Cliente Seleccionado",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_DANGER,
            fg="white",
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            command=self._eliminar_cliente_seleccionado,
        ).pack(anchor="e", pady=(10, 0))

        # Formulario agregar cliente
        tk.Label(der, text="REGISTRAR CLIENTE", font=("Segoe UI", 11, "bold"), fg=COLOR_SIDEBAR, bg="white").pack(
            anchor="w", pady=(0, 8)
        )
        self.var_cli_nombres = tk.StringVar()
        self.var_cli_apellidos = tk.StringVar()
        self.var_cli_calle = tk.StringVar()
        self.var_cli_ciudad = tk.StringVar()
        self.var_cli_pref = tk.StringVar()

        tk.Label(der, text="Nombres (*):", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        ttk.Entry(der, textvariable=self.var_cli_nombres).pack(fill=tk.X, pady=(0, 6))

        tk.Label(der, text="Apellidos (*):", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        ttk.Entry(der, textvariable=self.var_cli_apellidos).pack(fill=tk.X, pady=(0, 6))

        tk.Label(der, text="Calle / Dirección:", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        ttk.Entry(der, textvariable=self.var_cli_calle).pack(fill=tk.X, pady=(0, 6))

        tk.Label(der, text="Ciudad / Distrito:", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        ttk.Entry(der, textvariable=self.var_cli_ciudad).pack(fill=tk.X, pady=(0, 6))

        tk.Label(der, text="Usuario que lo atiende (*):", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        usuarios = self.db.obtener_usuarios_detallados()
        opciones_usr = [f"{u['id_usuario']} - {u['nombre']}" for u in usuarios]
        self.var_cli_usuario = tk.StringVar(value=opciones_usr[0] if opciones_usr else "")
        ttk.Combobox(der, textvariable=self.var_cli_usuario, values=opciones_usr, state="readonly").pack(fill=tk.X, pady=(0, 6))

        tk.Label(der, text="Preferencia inicial (opcional):", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        ttk.Entry(der, textvariable=self.var_cli_pref).pack(fill=tk.X, pady=(0, 12))

        tk.Button(
            der,
            text="💾 Guardar Cliente",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_SUCCESS,
            fg="white",
            bd=0,
            pady=9,
            cursor="hand2",
            command=self._guardar_nuevo_cliente,
        ).pack(fill=tk.X)

        self._refrescar_tabla_clientes()

    def _refrescar_tabla_clientes(self) -> None:
        for i in self.tree_clientes.get_children():
            self.tree_clientes.delete(i)
        if "cliente" not in self.db.tablas_disponibles or "usuario" not in self.db.tablas_disponibles:
            return

        if self.db.tiene_cliente_nombres_separados():
            sql = """
                SELECT c.codigo_cliente,
                       CONCAT(c.nombres, ' ', c.apellidos) AS cliente,
                       COALESCE(c.ciudad, '') AS ciudad,
                       COALESCE(c.calle, '') AS direccion,
                       u.nombre AS atendido_por,
                       GROUP_CONCAT(p.descripcion SEPARATOR ', ') AS preferencias
                FROM cliente c
                JOIN usuario u ON u.id_usuario = c.id_usuario
                LEFT JOIN cliente_preferencia cp ON cp.codigo_cliente = c.codigo_cliente
                LEFT JOIN preferencia p ON p.id_preferencia = cp.id_preferencia
                GROUP BY c.codigo_cliente, c.nombres, c.apellidos, c.ciudad, c.calle, u.nombre
                ORDER BY c.codigo_cliente
            """
        else:
            sql = """
                SELECT c.codigo_cliente,
                       c.nombre AS cliente,
                       COALESCE(c.ciudad, '') AS ciudad,
                       COALESCE(c.calle, '') AS direccion,
                       u.nombre AS atendido_por,
                       GROUP_CONCAT(cp.preferencia SEPARATOR ', ') AS preferencias
                FROM cliente c
                JOIN usuario u ON u.id_usuario = c.id_usuario
                LEFT JOIN cliente_preferencia cp ON cp.codigo_cliente = c.codigo_cliente
                GROUP BY c.codigo_cliente, c.nombre, c.ciudad, c.calle, u.nombre
                ORDER BY c.codigo_cliente
            """
        for r in self.db.consultar(sql):
            self.tree_clientes.insert(
                "",
                tk.END,
                iid=str(r["codigo_cliente"]),
                values=(
                    r["codigo_cliente"],
                    r["cliente"],
                    r["ciudad"] or "—",
                    r["direccion"] or "—",
                    r["atendido_por"],
                    r.get("preferencias") or "—",
                ),
            )

    def _guardar_nuevo_cliente(self) -> None:
        nom = self.var_cli_nombres.get().strip()
        ape = self.var_cli_apellidos.get().strip()
        if not nom or not ape:
            messagebox.showwarning("Datos incompletos", "Ingrese los nombres y apellidos del cliente.")
            return
        if not self.var_cli_usuario.get():
            messagebox.showwarning("Usuario requerido", "Seleccione el usuario que atiende al cliente.")
            return
        id_usr = int(self.var_cli_usuario.get().split("-")[0].strip())
        calle = self.var_cli_calle.get().strip() or None
        ciudad = self.var_cli_ciudad.get().strip() or None
        pref = self.var_cli_pref.get().strip()

        try:
            if self.db.tiene_cliente_nombres_separados():
                cod = self.db.ejecutar(
                    "INSERT INTO cliente (nombres, apellidos, calle, ciudad, id_usuario) VALUES (%s, %s, %s, %s, %s)",
                    (nom, ape, calle, ciudad, id_usr),
                )
                if pref and "preferencia" in self.db.tablas_disponibles:
                    exist = self.db.consultar("SELECT id_preferencia FROM preferencia WHERE descripcion = %s", (pref,))
                    if exist:
                        id_p = exist[0]["id_preferencia"]
                    else:
                        id_p = self.db.ejecutar("INSERT INTO preferencia (descripcion) VALUES (%s)", (pref,))
                    self.db.ejecutar(
                        "INSERT INTO cliente_preferencia (codigo_cliente, id_preferencia) VALUES (%s, %s)",
                        (cod, id_p),
                    )
            else:
                nombre_completo = f"{nom} {ape}"
                cod = self.db.ejecutar(
                    "INSERT INTO cliente (nombre, calle, ciudad, id_usuario) VALUES (%s, %s, %s, %s)",
                    (nombre_completo, calle, ciudad, id_usr),
                )
                if pref:
                    self.db.ejecutar(
                        "INSERT INTO cliente_preferencia (codigo_cliente, preferencia) VALUES (%s, %s)",
                        (cod, pref),
                    )
            self.var_cli_nombres.set("")
            self.var_cli_apellidos.set("")
            self.var_cli_calle.set("")
            self.var_cli_ciudad.set("")
            self.var_cli_pref.set("")
            self._refrescar_tabla_clientes()
            messagebox.showinfo("Cliente Registrado", f"Cliente registrado con código #{cod}.")
        except Exception as exc:
            messagebox.showerror("Error SQL", str(exc))

    def _eliminar_cliente_seleccionado(self) -> None:
        sel = self.tree_clientes.selection()
        if not sel:
            messagebox.showwarning("Selección requerida", "Seleccione un cliente de la tabla.")
            return
        cod = int(sel[0])
        if not messagebox.askyesno("Confirmar", f"¿Eliminar al cliente #{cod} y sus preferencias asociadas?"):
            return
        try:
            self.db.ejecutar("DELETE FROM cliente WHERE codigo_cliente = %s", (cod,))
            self._refrescar_tabla_clientes()
        except Exception as exc:
            messagebox.showerror("Error SQL", str(exc))

    # ==========================================================================
    # VISTA 4: AGENDA DE CITAS Y CICLO DE VIDA (RN-04)
    # ==========================================================================
    def _vista_citas(self) -> None:
        tk.Label(
            self.content_area,
            text="Agenda de Citas y Control del Ciclo de Vida (RN-04)",
            font=("Segoe UI", 14, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        ).pack(anchor="w", pady=(0, 10))

        split = tk.Frame(self.content_area, bg=COLOR_BG)
        split.pack(fill=tk.BOTH, expand=True)

        izq = tk.Frame(split, bg="white", highlightthickness=1, highlightbackground="#CBD5E1", padx=14, pady=12)
        izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        der = tk.Frame(split, bg="white", width=345, highlightthickness=1, highlightbackground="#CBD5E1", padx=16, pady=14)
        der.pack(side=tk.RIGHT, fill=tk.Y)
        der.pack_propagate(False)

        cols = ("num", "fecha", "inicio", "fin", "estado", "usuario", "servicios", "obs")
        self.tree_citas = ttk.Treeview(izq, columns=cols, show="headings")
        for cid, txt, w in [
            ("num", "N.º", 45),
            ("fecha", "Fecha", 85),
            ("inicio", "Inicio", 65),
            ("fin", "Fin", 65),
            ("estado", "Estado", 95),
            ("usuario", "Registrada por", 135),
            ("servicios", "Servicios (S/)", 170),
            ("obs", "Observaciones", 190),
        ]:
            self.tree_citas.heading(cid, text=txt)
            self.tree_citas.column(cid, width=w)
        self.tree_citas.pack(fill=tk.BOTH, expand=True)

        bar_citas = tk.Frame(izq, bg="white")
        bar_citas.pack(fill=tk.X, pady=(10, 0))

        for nuevo_est, color in [("Confirmada", "#2563EB"), ("Atendida", "#059669"), ("Cancelada", "#DC2626")]:
            tk.Button(
                bar_citas,
                text=f"Marcar '{nuevo_est}'",
                font=("Segoe UI", 9, "bold"),
                bg=color,
                fg="white",
                bd=0,
                padx=10,
                pady=6,
                cursor="hand2",
                command=lambda e=nuevo_est: self._cambiar_estado_cita(e),
            ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(
            bar_citas,
            text="🗑️ Eliminar Cita",
            font=("Segoe UI", 9, "bold"),
            bg="#FEE2E2",
            fg=COLOR_DANGER,
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._eliminar_cita,
        ).pack(side=tk.RIGHT)

        # Formulario Nueva Cita
        tk.Label(der, text="PROGRAMAR NUEVA CITA", font=("Segoe UI", 11, "bold"), fg=COLOR_SIDEBAR, bg="white").pack(
            anchor="w", pady=(0, 8)
        )
        self.var_cita_fecha = tk.StringVar(value=dt.date.today().strftime("%Y-%m-%d"))
        self.var_cita_hora = tk.StringVar(value="10:00")
        self.var_cita_obs = tk.StringVar()

        tk.Label(der, text="Fecha (AAAA-MM-DD):", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        ttk.Entry(der, textvariable=self.var_cita_fecha).pack(fill=tk.X, pady=(0, 6))

        tk.Label(der, text="Hora de Inicio (HH:MM):", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        ttk.Entry(der, textvariable=self.var_cita_hora).pack(fill=tk.X, pady=(0, 6))

        tk.Label(der, text="Servicio Solicitado (*):", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        servicios = (
            self.db.consultar("SELECT codigo_servicio, nombre, precio, duracion FROM servicio ORDER BY codigo_servicio")
            if "servicio" in self.db.tablas_disponibles
            else []
        )
        opc_srv = [f"{s['codigo_servicio']} - {s['nombre']} (S/ {float(s['precio']):.2f}, {s['duracion']}m)" for s in servicios]
        self.var_cita_srv = tk.StringVar(value=opc_srv[0] if opc_srv else "")
        ttk.Combobox(der, textvariable=self.var_cita_srv, values=opc_srv, state="readonly").pack(fill=tk.X, pady=(0, 6))

        tk.Label(der, text="Estado Inicial (*):", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        estados = (
            self.db.consultar("SELECT id_estado, descripcion FROM estado_cita ORDER BY id_estado")
            if "estado_cita" in self.db.tablas_disponibles
            else []
        )
        opc_est = [f"{e['id_estado']} - {e['descripcion']}" for e in estados]
        self.var_cita_est = tk.StringVar(value=opc_est[0] if opc_est else "")
        ttk.Combobox(der, textvariable=self.var_cita_est, values=opc_est, state="readonly").pack(fill=tk.X, pady=(0, 6))

        tk.Label(der, text="Usuario que registra (*):", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        usuarios = self.db.obtener_usuarios_detallados()
        opc_usr = [f"{u['id_usuario']} - {u['nombre']} ({u['rol']})" for u in usuarios]
        self.var_cita_usr = tk.StringVar(value=opc_usr[0] if opc_usr else "")
        ttk.Combobox(der, textvariable=self.var_cita_usr, values=opc_usr, state="readonly").pack(fill=tk.X, pady=(0, 6))

        tk.Label(der, text="Observaciones / Cliente:", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        ttk.Entry(der, textvariable=self.var_cita_obs).pack(fill=tk.X, pady=(0, 12))

        tk.Button(
            der,
            text="💾 Registrar Cita",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_SUCCESS,
            fg="white",
            bd=0,
            pady=9,
            cursor="hand2",
            command=self._guardar_nueva_cita,
        ).pack(fill=tk.X)

        self._refrescar_tabla_citas()

    def _refrescar_tabla_citas(self) -> None:
        for i in self.tree_citas.get_children():
            self.tree_citas.delete(i)
        if "cita" not in self.db.tablas_disponibles or "estado_cita" not in self.db.tablas_disponibles:
            return
        sql = """
            SELECT c.numero_registro,
                   c.fecha,
                   c.hora_inicio,
                   COALESCE(c.hora_fin, '') AS hora_fin,
                   e.descripcion AS estado,
                   u.nombre AS usuario,
                   COALESCE(c.observaciones, '') AS observaciones,
                   GROUP_CONCAT(CONCAT(s.nombre, ' (S/', cs.precio, ')') SEPARATOR ', ') AS servicios
            FROM cita c
            JOIN estado_cita e ON e.id_estado = c.id_estado
            JOIN usuario u ON u.id_usuario = c.id_usuario
            LEFT JOIN cita_servicio cs ON cs.numero_registro = c.numero_registro
            LEFT JOIN servicio s ON s.codigo_servicio = cs.codigo_servicio
            GROUP BY c.numero_registro, c.fecha, c.hora_inicio, c.hora_fin, e.descripcion, u.nombre, c.observaciones
            ORDER BY c.numero_registro DESC
        """
        for r in self.db.consultar(sql):
            self.tree_citas.insert(
                "",
                tk.END,
                iid=str(r["numero_registro"]),
                values=(
                    r["numero_registro"],
                    str(r["fecha"]),
                    str(r["hora_inicio"]),
                    str(r["hora_fin"]),
                    r["estado"],
                    r["usuario"],
                    r.get("servicios") or "—",
                    r["observaciones"],
                ),
            )

    def _guardar_nueva_cita(self) -> None:
        try:
            fecha = self.var_cita_fecha.get().strip()
            h_ini_str = self.var_cita_hora.get().strip()
            if len(h_ini_str) == 5:
                h_ini_str += ":00"
            h_ini = dt.datetime.strptime(h_ini_str, "%H:%M:%S")
            cod_srv = int(self.var_cita_srv.get().split("-")[0].strip())
            id_est = int(self.var_cita_est.get().split("-")[0].strip())
            id_usr = int(self.var_cita_usr.get().split("-")[0].strip())
            obs = self.var_cita_obs.get().strip() or None

            srv_row = self.db.consultar(
                "SELECT precio, duracion FROM servicio WHERE codigo_servicio = %s", (cod_srv,)
            )[0]
            h_fin = (h_ini + dt.timedelta(minutes=int(srv_row["duracion"]))).strftime("%H:%M:%S")

            num = self.db.ejecutar(
                "INSERT INTO cita (fecha, hora_inicio, hora_fin, observaciones, id_estado, id_usuario) VALUES (%s, %s, %s, %s, %s, %s)",
                (fecha, h_ini.strftime("%H:%M:%S"), h_fin, obs, id_est, id_usr),
            )
            self.db.ejecutar(
                "INSERT INTO cita_servicio (numero_registro, codigo_servicio, precio) VALUES (%s, %s, %s)",
                (num, cod_srv, srv_row["precio"]),
            )
            self._refrescar_tabla_citas()
            messagebox.showinfo("Cita Programada", f"Se registró la cita #{num} ({h_ini.strftime('%H:%M')} - {h_fin[:5]}).")
        except Exception as exc:
            messagebox.showerror("Error al registrar cita", str(exc))

    def _cambiar_estado_cita(self, nombre_estado: str) -> None:
        sel = self.tree_citas.selection()
        if not sel:
            messagebox.showwarning("Selección requerida", "Seleccione una cita de la lista.")
            return
        num = int(sel[0])
        filas = self.db.consultar("SELECT id_estado FROM estado_cita WHERE descripcion = %s", (nombre_estado,))
        if not filas:
            return
        self.db.ejecutar("UPDATE cita SET id_estado = %s WHERE numero_registro = %s", (filas[0]["id_estado"], num))
        self._refrescar_tabla_citas()

    def _eliminar_cita(self) -> None:
        sel = self.tree_citas.selection()
        if not sel:
            return
        num = int(sel[0])
        if messagebox.askyesno("Confirmar", f"¿Eliminar la cita #{num}?"):
            self.db.ejecutar("DELETE FROM cita WHERE numero_registro = %s", (num,))
            self._refrescar_tabla_citas()

    # ==========================================================================
    # VISTA 5: INVENTARIO (POR BOTELLAS), VENTAS Y PEDIDOS (RN-06, RN-07, RN-08)
    # ==========================================================================
    def _vista_inventario(self) -> None:
        tk.Label(
            self.content_area,
            text="Control de Inventario (por Unidades/Botellas), Ventas y Reposición de Stock",
            font=("Segoe UI", 14, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        ).pack(anchor="w", pady=(0, 10))

        split = tk.Frame(self.content_area, bg=COLOR_BG)
        split.pack(fill=tk.BOTH, expand=True)

        izq = tk.Frame(split, bg="white", highlightthickness=1, highlightbackground="#CBD5E1", padx=14, pady=12)
        izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        der = tk.Frame(split, bg="white", width=350, highlightthickness=1, highlightbackground="#CBD5E1", padx=16, pady=14)
        der.pack(side=tk.RIGHT, fill=tk.Y)
        der.pack_propagate(False)

        cols = ("cod", "nombre", "presentacion", "precio", "stock")
        self.tree_prod = ttk.Treeview(izq, columns=cols, show="headings")
        for cid, txt, w, al in [
            ("cod", "Cód.", 55, tk.CENTER),
            ("nombre", "Producto", 210, tk.W),
            ("presentacion", "Presentación / Unidad", 190, tk.W),
            ("precio", "Precio Unit. (S/)", 110, tk.E),
            ("stock", "Stock (Botellas/Und)", 130, tk.CENTER),
        ]:
            self.tree_prod.heading(cid, text=txt)
            self.tree_prod.column(cid, width=w, anchor=al)
        self.tree_prod.pack(fill=tk.BOTH, expand=True)

        # Panel derecho: Registrar Venta Directa (Descuenta Stock)
        tk.Label(der, text="REGISTRAR VENTA DE PRODUCTO", font=("Segoe UI", 11, "bold"), fg=COLOR_SIDEBAR, bg="white").pack(
            anchor="w", pady=(0, 6)
        )
        prods = (
            self.db.consultar("SELECT codigo_producto, nombre, precio_unitario, stock FROM producto ORDER BY codigo_producto")
            if "producto" in self.db.tablas_disponibles
            else []
        )
        opc_p = [f"{p['codigo_producto']} - {p['nombre']} (Stock: {p['stock']})" for p in prods]

        self.var_vta_prod = tk.StringVar(value=opc_p[0] if opc_p else "")
        self.var_vta_cant = tk.StringVar(value="1")

        tk.Label(der, text="Producto a vender:", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        self.combo_vta_prod = ttk.Combobox(der, textvariable=self.var_vta_prod, values=opc_p, state="readonly")
        self.combo_vta_prod.pack(fill=tk.X, pady=(0, 6))

        tk.Label(der, text="Cantidad (Botellas/Unidades > 0):", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        ttk.Entry(der, textvariable=self.var_vta_cant).pack(fill=tk.X, pady=(0, 8))

        tk.Button(
            der,
            text="🛒 Registrar Venta (Descuenta Stock)",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_SUCCESS,
            fg="white",
            bd=0,
            pady=8,
            cursor="hand2",
            command=self._registrar_venta_rapida,
        ).pack(fill=tk.X, pady=(0, 16))

        ttk.Separator(der, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # Registrar Pedido a Proveedor (Aumenta Stock)
        tk.Label(der, text="REPOSICIÓN A PROVEEDOR (+STOCK)", font=("Segoe UI", 11, "bold"), fg=COLOR_PRIMARY, bg="white").pack(
            anchor="w", pady=(4, 6)
        )
        self.var_ped_cant = tk.StringVar(value="10")
        tk.Label(der, text="Cantidad recibida (Botellas > 0):", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        ttk.Entry(der, textvariable=self.var_ped_cant).pack(fill=tk.X, pady=(0, 8))

        tk.Button(
            der,
            text="📦 Registrar Ingreso de Lote (+Stock)",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_PRIMARY,
            fg="white",
            bd=0,
            pady=8,
            cursor="hand2",
            command=self._registrar_pedido_rapido,
        ).pack(fill=tk.X)

        self._refrescar_tabla_productos()

    def _refrescar_tabla_productos(self) -> None:
        for i in self.tree_prod.get_children():
            self.tree_prod.delete(i)
        if "producto" not in self.db.tablas_disponibles:
            return
        filas = self.db.consultar(
            "SELECT codigo_producto, nombre, COALESCE(descripcion, '') AS descripcion, precio_unitario, stock FROM producto ORDER BY codigo_producto"
        )
        for r in filas:
            self.tree_prod.insert(
                "",
                tk.END,
                values=(
                    r["codigo_producto"],
                    r["nombre"],
                    r["descripcion"],
                    f"{float(r['precio_unitario']):.2f}",
                    r["stock"],
                ),
            )
        opc_p = [f"{p['codigo_producto']} - {p['nombre']} (Stock: {p['stock']})" for p in filas]
        self.combo_vta_prod.configure(values=opc_p)
        if opc_p:
            self.var_vta_prod.set(opc_p[0])

    def _registrar_venta_rapida(self) -> None:
        try:
            cod_p = int(self.var_vta_prod.get().split("-")[0].strip())
            cant = int(self.var_vta_cant.get().strip())
            if cant <= 0:
                raise ValueError("La cantidad debe ser estrictamente mayor a 0 (RN-06).")

            prod = self.db.consultar("SELECT nombre, precio_unitario, stock FROM producto WHERE codigo_producto = %s", (cod_p,))[0]
            if int(prod["stock"]) < cant:
                raise ValueError(f"Stock insuficiente para completar la venta (RN-08). Disponible: {prod['stock']} unidades.")

            # Verificar si existen triggers activos en esta BD
            triggers = self.db.consultar("SHOW TRIGGERS LIKE 'detalle_venta'")
            tiene_trigger = any("descuenta_stock" in str(t.values()) for t in triggers)

            hoy = dt.date.today().strftime("%Y-%m-%d")
            num_venta = self.db.ejecutar("INSERT INTO venta (fecha, total) VALUES (%s, 0)", (hoy,))
            precio = float(prod["precio_unitario"])
            self.db.ejecutar(
                "INSERT INTO detalle_venta (numero_venta, codigo_producto, cantidad, precio) VALUES (%s, %s, %s, %s)",
                (num_venta, cod_p, cant, precio),
            )
            if not tiene_trigger:
                self.db.ejecutar(
                    "UPDATE producto SET stock = stock - %s WHERE codigo_producto = %s",
                    (cant, cod_p),
                )
                self.db.ejecutar(
                    "UPDATE venta SET total = %s WHERE numero_venta = %s",
                    (cant * precio, num_venta),
                )
            self._refrescar_tabla_productos()
            messagebox.showinfo(
                "Venta Registrada",
                f"Venta #{num_venta} registrada: {cant} und. de '{prod['nombre']}' (Total: S/ {cant * precio:.2f}).",
            )
        except Exception as exc:
            messagebox.showerror("Error en Venta (RN-06 / RN-08)", str(exc))

    def _registrar_pedido_rapido(self) -> None:
        try:
            cod_p = int(self.var_vta_prod.get().split("-")[0].strip())
            cant = int(self.var_ped_cant.get().strip())
            if cant <= 0:
                raise ValueError("La cantidad del pedido debe ser mayor a 0.")

            prod = self.db.consultar("SELECT nombre, precio_unitario FROM producto WHERE codigo_producto = %s", (cod_p,))[0]
            usr = self.db.consultar("SELECT id_usuario FROM usuario ORDER BY id_usuario LIMIT 1")[0]["id_usuario"]
            prov = self.db.consultar("SELECT codigo_proveedor FROM proveedor ORDER BY codigo_proveedor LIMIT 1")[0]["codigo_proveedor"]

            triggers = self.db.consultar("SHOW TRIGGERS LIKE 'detalle_pedido'")
            tiene_trigger = any("aumenta_stock" in str(t.values()) for t in triggers)

            hoy = dt.date.today().strftime("%Y-%m-%d")
            id_ped = self.db.ejecutar(
                "INSERT INTO pedido_compra (fecha, id_usuario, codigo_proveedor) VALUES (%s, %s, %s)",
                (hoy, usr, prov),
            )
            costo = round(float(prod["precio_unitario"]) * 0.65, 2)
            self.db.ejecutar(
                "INSERT INTO detalle_pedido (id_pedido, codigo_producto, cantidad, precio) VALUES (%s, %s, %s, %s)",
                (id_ped, cod_p, cant, costo),
            )
            if not tiene_trigger:
                self.db.ejecutar(
                    "UPDATE producto SET stock = stock + %s WHERE codigo_producto = %s",
                    (cant, cod_p),
                )
            self._refrescar_tabla_productos()
            messagebox.showinfo("Stock Incrementado", f"Pedido #{id_ped} registrado: +{cant} botellas de '{prod['nombre']}'.")
        except Exception as exc:
            messagebox.showerror("Error en Pedido", str(exc))

    # ==========================================================================
    # VISTA 6: EXPLORADOR DIRECTO DE TABLAS SQL
    # ==========================================================================
    def _vista_explorador(self) -> None:
        top = tk.Frame(self.content_area, bg=COLOR_BG)
        top.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            top,
            text="Explorador Directo de Tablas de la Base de Datos",
            font=("Segoe UI", 14, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        ).pack(side=tk.LEFT)

        bar = tk.Frame(self.content_area, bg="white", highlightthickness=1, highlightbackground="#CBD5E1", padx=12, pady=10)
        bar.pack(fill=tk.X, pady=(0, 10))

        tk.Label(bar, text="Seleccionar Tabla:", font=("Segoe UI", 10, "bold"), bg="white").pack(side=tk.LEFT, padx=(0, 8))
        tablas = sorted(self.db.tablas_disponibles)
        self.var_tabla_exp = tk.StringVar(value=tablas[0] if tablas else "")
        combo = ttk.Combobox(bar, textvariable=self.var_tabla_exp, values=tablas, state="readonly", width=28)
        combo.pack(side=tk.LEFT)

        self.lbl_conteo_exp = tk.Label(bar, text="", font=("Segoe UI", 9, "bold"), fg=COLOR_PRIMARY, bg="white")
        self.lbl_conteo_exp.pack(side=tk.LEFT, padx=16)

        frame_t = tk.Frame(self.content_area, bg="white", highlightthickness=1, highlightbackground="#CBD5E1")
        frame_t.pack(fill=tk.BOTH, expand=True)

        sy = ttk.Scrollbar(frame_t, orient=tk.VERTICAL)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        sx = ttk.Scrollbar(frame_t, orient=tk.HORIZONTAL)
        sx.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree_exp = ttk.Treeview(frame_t, show="headings", yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.config(command=self.tree_exp.yview)
        sx.config(command=self.tree_exp.xview)
        self.tree_exp.pack(fill=tk.BOTH, expand=True)

        combo.bind("<<ComboboxSelected>>", lambda _e: self._cargar_tabla_explorador())
        self._cargar_tabla_explorador()

    def _cargar_tabla_explorador(self) -> None:
        t = self.var_tabla_exp.get()
        if not t or t not in self.db.tablas_disponibles:
            return
        for item in self.tree_exp.get_children():
            self.tree_exp.delete(item)

        cols = self.db.columnas_por_tabla.get(t, [])
        self.tree_exp["columns"] = cols
        for c in cols:
            self.tree_exp.heading(c, text=c)
            self.tree_exp.column(c, width=130, anchor=tk.W)

        filas = self.db.consultar(f"SELECT * FROM `{t}` LIMIT 500")
        for f in filas:
            self.tree_exp.insert("", tk.END, values=[f.get(c, "") if f.get(c) is not None else "NULL" for c in cols])
        self.lbl_conteo_exp.configure(text=f"Mostrando {len(filas)} registros en `{t}` ({len(cols)} columnas)")


def main() -> None:
    params = obtener_parametros_conexion()
    try:
        gestor = GestorBaseDatos(params)
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error de Conexión a MySQL", f"No se pudo conectar a la base de datos:\n{exc}")
        sys.exit(1)

    app = SistemaSpaRodriguezApp(gestor)
    app.mainloop()


if __name__ == "__main__":
    main()
