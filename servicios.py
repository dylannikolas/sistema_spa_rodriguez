# -*- coding: utf-8 -*-
"""
Capa de servicios y acceso a datos (T1, T2, T4, T6, T7, T8, T9, T10, T11).
Encapsula las llamadas a los Procedimientos Almacenados SQL (`callproc`),
la verificación de permisos por rol (`@requiere_rol`) y el registro en bitácora.
"""
from __future__ import annotations

import json
import re
from mysql.connector import Error as MySQLError

from auth import GestorAutenticacion, sugerir_username
from db import ConexionBaseDatos
from permisos import ROL_ADMIN, ROL_TRABAJADOR, ROLES_VALIDOS, SesionUsuario, requiere_rol
from seguridad import generar_clave_temporal, generar_hash_contrasena


class GestorBaseDatos(ConexionBaseDatos):
    """
    Fachada de servicios de datos del Salón Spa Rodríguez.
    Controla transacciones desde Python, exige autorización por rol en cada método sensible
    y delega las operaciones críticas en los Procedimientos Almacenados SQL (`sp_*`).
    """

    def __init__(
        self,
        params: dict[str, str | int] | None = None,
        sesion: SesionUsuario | None = None,
        autocommit_transaccion: bool = True,
    ):
        super().__init__(params=params, autocommit_transaccion=autocommit_transaccion)
        self.sesion_actual: SesionUsuario | None = sesion
        self.auth = GestorAutenticacion(self)

    # ------------------------------------------------------------------
    # AUTENTICACIÓN Y GESTIÓN DE SESIÓN (T3, T4, T11)
    # ------------------------------------------------------------------
    def iniciar_sesion(self, username: str, contrasena: str) -> SesionUsuario:
        """Autentica al operador y establece `self.sesion_actual`."""
        sesion = self.auth.autenticar(username, contrasena)
        self.sesion_actual = sesion
        return sesion

    def cerrar_sesion(self) -> None:
        """Cierra la sesión activa registrando el evento en la bitácora."""
        if self.sesion_actual is not None:
            self.auth.registrar_bitacora(
                "LOGOUT",
                "Cierre de sesión del operador.",
                id_usuario=self.sesion_actual.id_usuario,
                username=self.sesion_actual.username,
            )
        self.sesion_actual = None

    def cambiar_contrasena_propia(self, clave_actual: str, clave_nueva: str) -> None:
        """Cambia la contraseña del usuario en sesión y habilita su operación si era temporal."""
        if self.sesion_actual is None:
            raise PermissionError("Debe iniciar sesión para cambiar su contraseña.")
        self.auth.cambiar_contrasena(self.sesion_actual.id_usuario, clave_actual, clave_nueva)
        self.sesion_actual.debe_cambiar = False

    def _log(self, accion: str, detalle: str, commit: bool | None = None) -> None:
        uid = self.sesion_actual.id_usuario if self.sesion_actual else None
        usr = self.sesion_actual.username if self.sesion_actual else None
        self.auth.registrar_bitacora(accion, detalle, id_usuario=uid, username=usr, commit=commit)

    # ------------------------------------------------------------------
    # CATÁLOGOS OFICIALES (18 TABLAS)
    # ------------------------------------------------------------------
    def listar_especialidades(self) -> list[str]:
        filas = self.consultar("SELECT nombre_especialidad FROM especialidad ORDER BY nombre_especialidad")
        return [str(f["nombre_especialidad"]) for f in filas if f.get("nombre_especialidad")]

    def listar_preferencias_catalogo(self) -> list[str]:
        """Devuelve exclusivamente las preferencias del catálogo oficial (T9: O12)."""
        filas = self.consultar("SELECT descripcion FROM preferencia ORDER BY descripcion")
        return [str(f["descripcion"]) for f in filas if f.get("descripcion")]

    def listar_estados_cita(self) -> list[str]:
        filas = self.consultar("SELECT descripcion FROM estado_cita ORDER BY id_estado")
        return [str(f["descripcion"]) for f in filas if f.get("descripcion")]

    def _obtener_id_especialidad(self, cur, nombre_esp: str) -> int:
        cur.execute("SELECT id_especialidad FROM especialidad WHERE nombre_especialidad = %s", (nombre_esp,))
        fila = cur.fetchone()
        if not fila:
            raise ValueError(f"La especialidad '{nombre_esp}' no existe en el catálogo oficial.")
        return int(fila[0])

    # ------------------------------------------------------------------
    # ADMINISTRACIÓN DE USUARIOS Y CREDENCIALES (T3, T4, T6)
    # ------------------------------------------------------------------
    def contar_administradores_activos(self, excluir_id_usuario: int | None = None) -> int:
        esquema_auth = self.nombre_bd_auth
        if excluir_id_usuario is not None:
            filas = self.consultar(
                f"""
                SELECT COUNT(*) AS n
                  FROM `{esquema_auth}`.`credencial`
                 WHERE rol = %s AND activo = 1 AND id_usuario <> %s
                """,
                (ROL_ADMIN, excluir_id_usuario),
            )
        else:
            filas = self.consultar(
                f"""
                SELECT COUNT(*) AS n
                  FROM `{esquema_auth}`.`credencial`
                 WHERE rol = %s AND activo = 1
                """,
                (ROL_ADMIN,),
            )
        return int(filas[0]["n"]) if filas else 0

    @requiere_rol(ROL_ADMIN, ROL_TRABAJADOR)
    def obtener_usuarios_detallados(self, filtro_rol: str = "TODOS", busqueda: str = "") -> list[dict]:
        """
        Devuelve los usuarios uniendo `spa_rodriguez.usuario` con `spa_rodriguez_app.credencial`.
        - El rol proviene explícitamente de `credencial.rol` (T4: O5), nunca de `empleado`.
        - Jamás incluye contraseñas ni hashes en el resultado (T3: O4).
        """
        esquema_auth = self.nombre_bd_auth
        sql = f"""
            SELECT u.id_usuario,
                   u.nombre,
                   COALESCE(u.telefono, '') AS telefono,
                   COALESCE(c.username, '') AS username,
                   COALESCE(c.rol, 'TRABAJADOR') AS rol_codigo,
                   COALESCE(c.activo, 1) AS activo,
                   COALESCE(c.debe_cambiar, 0) AS debe_cambiar,
                   COALESCE(c.intentos_fallidos, 0) AS intentos_fallidos,
                   c.bloqueado_hasta,
                   c.ultimo_acceso,
                   GROUP_CONCAT(DISTINCT e.codigo_empleado ORDER BY e.codigo_empleado SEPARATOR ', ') AS codigos_empleado,
                   GROUP_CONCAT(DISTINCT esp.nombre_especialidad ORDER BY esp.nombre_especialidad SEPARATOR ', ') AS especialidad,
                   GROUP_CONCAT(DISTINCT a.codigo_almacen ORDER BY a.codigo_almacen SEPARATOR ', ') AS almacenes,
                   (SELECT COUNT(*) FROM cliente cl WHERE cl.id_usuario = u.id_usuario) AS total_clientes,
                   (SELECT COUNT(*) FROM cita ci WHERE ci.id_usuario = u.id_usuario) AS total_citas,
                   (SELECT COUNT(*) FROM pedido_compra p WHERE p.id_usuario = u.id_usuario) AS total_pedidos
              FROM usuario u
              LEFT JOIN `{esquema_auth}`.`credencial` c ON c.id_usuario = u.id_usuario
              LEFT JOIN empleado e ON e.id_usuario = u.id_usuario
              LEFT JOIN especialidad esp ON esp.id_especialidad = e.id_especialidad
              LEFT JOIN almacen a ON a.id_usuario = u.id_usuario
             GROUP BY u.id_usuario, u.nombre, u.telefono,
                      c.username, c.rol, c.activo, c.debe_cambiar,
                      c.intentos_fallidos, c.bloqueado_hasta, c.ultimo_acceso
             ORDER BY u.id_usuario
        """
        filas = self.consultar(sql)
        resultado: list[dict] = []
        q = (busqueda or "").strip().lower()
        filtro = (filtro_rol or "TODOS").strip().upper()

        for f in filas:
            rol_cod = str(f.get("rol_codigo") or ROL_TRABAJADOR).upper()
            rol_etiqueta = "Administrador" if rol_cod == ROL_ADMIN else "Trabajador"
            f["rol_codigo"] = rol_cod
            f["rol"] = rol_etiqueta
            f["username"] = str(f.get("username") or sugerir_username(str(f["nombre"]), int(f["id_usuario"])))
            f["especialidad_mostrar"] = f.get("especialidad") or (
                "Administración / Recepción / Almacén" if rol_cod == ROL_ADMIN else "Sin especialidad asignada"
            )
            f["almacenes_mostrar"] = f"Almacén #{f['almacenes']}" if f.get("almacenes") else "—"
            f["estado_cuenta"] = (
                "Activa (Cambio clave pend.)"
                if f.get("activo") and f.get("debe_cambiar")
                else ("Activa" if f.get("activo") else "Inactiva")
            )

            if filtro in ("ADMIN", "ADMINISTRADOR") and rol_cod != ROL_ADMIN:
                continue
            if filtro == "TRABAJADOR" and rol_cod != ROL_TRABAJADOR:
                continue
            if q:
                texto = f"{f['id_usuario']} {f['username']} {f['nombre']} {f['telefono']} {rol_etiqueta} {f['especialidad_mostrar']}".lower()
                if q not in texto:
                    continue
            resultado.append(f)
        return resultado

    @requiere_rol(ROL_ADMIN)
    def agregar_usuario(
        self,
        nombre: str,
        telefono: str | None,
        rol: str = ROL_TRABAJADOR,
        especialidad: str = "",
        registrar_almacen: bool = False,
        username: str = "",
    ) -> tuple[int, str]:
        """
        Crea un nuevo usuario en `usuario` y su credencial en `spa_rodriguez_app.credencial`
        con el rol de menor privilegio por defecto (`TRABAJADOR`) y una contraseña temporal
        aleatoria (`debe_cambiar = 1`). Retorna `(id_usuario, clave_temporal)`.
        """
        nom = (nombre or "").strip()
        if len(nom) < 2:
            raise ValueError("El nombre del usuario es obligatorio (mínimo 2 caracteres).")

        tel_limpio = (telefono or "").strip() or None
        if tel_limpio is not None and not re.fullmatch(r"[0-9]{9}", tel_limpio):
            raise ValueError("El teléfono debe tener exactamente 9 dígitos numéricos o dejarse vacío.")

        rol_norm = ROL_ADMIN if rol.strip().upper() in ("ADMIN", "ADMINISTRADOR") else ROL_TRABAJADOR
        esp_txt = (especialidad or "").strip()
        if rol_norm == ROL_TRABAJADOR and not esp_txt:
            raise ValueError("Para el rol 'Trabajador' debe seleccionar una especialidad del catálogo.")

        usr_limpio = (username or "").strip().lower() or sugerir_username(nom)
        if " " in usr_limpio or usr_limpio.isdigit():
            raise ValueError("El nombre de usuario (username) no puede contener espacios ni ser solo numérico.")

        clave_temporal = generar_clave_temporal()
        hash_hex, salt_hex, iters = generar_hash_contrasena(clave_temporal)

        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO usuario (nombre, telefono) VALUES (%s, %s)",
                (nom, tel_limpio),
            )
            id_usuario = int(cur.lastrowid)

            if esp_txt:
                id_esp = self._obtener_id_especialidad(cur, esp_txt)
                cur.execute(
                    "INSERT INTO empleado (id_especialidad, id_usuario) VALUES (%s, %s)",
                    (id_esp, id_usuario),
                )

            if registrar_almacen:
                cur.execute("INSERT INTO almacen (id_usuario) VALUES (%s)", (id_usuario,))

            cur.execute(
                f"""
                INSERT INTO `{self.nombre_bd_auth}`.`credencial`
                    (id_usuario, username, rol, hash_clave, salt, iteraciones, activo, debe_cambiar, intentos_fallidos)
                VALUES (%s, %s, %s, %s, %s, %s, 1, 1, 0)
                """,
                (id_usuario, usr_limpio, rol_norm, hash_hex, salt_hex, iters),
            )
            self._log(
                "ALTA_USUARIO",
                f"Creado usuario ID {id_usuario} ('{usr_limpio}') con rol {rol_norm} y clave temporal.",
                commit=False,
            )
            if self.autocommit_transaccion:
                conn.commit()
            return id_usuario, clave_temporal
        except MySQLError as err:
            if self.autocommit_transaccion:
                conn.rollback()
            raise ValueError(f"No se pudo crear el usuario: {err.msg}") from err
        except Exception:
            if self.autocommit_transaccion:
                conn.rollback()
            raise
        finally:
            cur.close()

    @requiere_rol(ROL_ADMIN)
    def actualizar_usuario(
        self,
        id_usuario: int,
        nombre: str,
        telefono: str | None,
        rol: str,
        especialidad: str = "",
        username: str = "",
        activo: bool = True,
    ) -> None:
        """
        Actualiza datos del usuario y su rol en `credencial` sin borrar jamás su fila en `empleado` (T4: O5).
        Protege contra auto-degradación o auto-desactivación del administrador en sesión (T6).
        """
        assert self.sesion_actual is not None
        nom = (nombre or "").strip()
        if len(nom) < 2:
            raise ValueError("El nombre del usuario es obligatorio (mínimo 2 caracteres).")

        tel_limpio = (telefono or "").strip() or None
        if tel_limpio is not None and not re.fullmatch(r"[0-9]{9}", tel_limpio):
            raise ValueError("El teléfono debe tener exactamente 9 dígitos numéricos o dejarse vacío.")

        rol_norm = ROL_ADMIN if rol.strip().upper() in ("ADMIN", "ADMINISTRADOR") else ROL_TRABAJADOR

        if id_usuario == self.sesion_actual.id_usuario:
            if rol_norm != ROL_ADMIN:
                raise PermissionError("Un administrador no puede quitarse el rol de Administrador a sí mismo.")
            if not activo:
                raise PermissionError("Un administrador no puede desactivar su propia cuenta.")

        if (rol_norm != ROL_ADMIN or not activo) and self.contar_administradores_activos(excluir_id_usuario=id_usuario) == 0:
            raise PermissionError("El sistema no puede quedar sin al menos un Administrador activo.")

        usr_limpio = (username or "").strip().lower() or sugerir_username(nom, id_usuario)
        esp_txt = (especialidad or "").strip()

        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE usuario SET nombre = %s, telefono = %s WHERE id_usuario = %s",
                (nom, tel_limpio, id_usuario),
            )
            cur.execute(
                f"""
                UPDATE `{self.nombre_bd_auth}`.`credencial`
                   SET username = %s, rol = %s, activo = %s
                 WHERE id_usuario = %s
                """,
                (usr_limpio, rol_norm, 1 if activo else 0, id_usuario),
            )

            # T4: Cambiar de rol NO borra filas de `empleado`. Solo actualiza o inserta especialidad si se indica.
            if esp_txt and esp_txt not in ("Administración / Recepción / Almacén", "Sin especialidad asignada"):
                id_esp = self._obtener_id_especialidad(cur, esp_txt)
                cur.execute("SELECT codigo_empleado FROM empleado WHERE id_usuario = %s", (id_usuario,))
                emp_existente = cur.fetchone()
                if emp_existente:
                    cur.execute(
                        "UPDATE empleado SET id_especialidad = %s WHERE id_usuario = %s",
                        (id_esp, id_usuario),
                    )
                else:
                    cur.execute(
                        "INSERT INTO empleado (id_especialidad, id_usuario) VALUES (%s, %s)",
                        (id_esp, id_usuario),
                    )

            self._log(
                "ACTUALIZAR_USUARIO",
                f"Actualizado usuario ID {id_usuario} ('{usr_limpio}', rol={rol_norm}, activo={activo}).",
                commit=False,
            )
            if self.autocommit_transaccion:
                conn.commit()
        except MySQLError as err:
            if self.autocommit_transaccion:
                conn.rollback()
            raise ValueError(f"Error al actualizar el usuario: {err.msg}") from err
        except Exception:
            if self.autocommit_transaccion:
                conn.rollback()
            raise
        finally:
            cur.close()

    @requiere_rol(ROL_ADMIN)
    def restablecer_contrasena_usuario(self, id_usuario: int) -> str:
        """Restablece la contraseña de un usuario generando una clave temporal de un solo uso."""
        assert self.sesion_actual is not None
        return self.auth.restablecer_clave_temporal(id_usuario, self.sesion_actual)

    def obtener_dependencias_usuario(self, id_usuario: int) -> dict[str, int]:
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

    @requiere_rol(ROL_ADMIN)
    def eliminar_usuario(self, id_usuario: int, id_usuario_reasignar: int | None = None) -> None:
        assert self.sesion_actual is not None
        if id_usuario == self.sesion_actual.id_usuario:
            raise PermissionError("Un administrador no puede eliminarse a sí mismo.")
        if self.contar_administradores_activos(excluir_id_usuario=id_usuario) == 0:
            raise PermissionError("No se puede eliminar al único Administrador activo del sistema.")

        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            if id_usuario_reasignar is not None:
                if id_usuario_reasignar == id_usuario:
                    raise ValueError("El usuario de reasignación debe ser distinto al usuario a eliminar.")
                for tabla in ("cliente", "cita", "almacen", "pedido_compra"):
                    cur.execute(
                        f"UPDATE `{tabla}` SET id_usuario = %s WHERE id_usuario = %s",
                        (id_usuario_reasignar, id_usuario),
                    )

            cur.execute("DELETE FROM empleado WHERE id_usuario = %s", (id_usuario,))
            cur.execute(
                f"DELETE FROM `{self.nombre_bd_auth}`.`credencial` WHERE id_usuario = %s",
                (id_usuario,),
            )
            cur.execute("DELETE FROM usuario WHERE id_usuario = %s", (id_usuario,))
            self._log(
                "ELIMINAR_USUARIO",
                f"Eliminado usuario ID {id_usuario} (reasignado a {id_usuario_reasignar}).",
                commit=False,
            )
            if self.autocommit_transaccion:
                conn.commit()
        except MySQLError as err:
            if self.autocommit_transaccion:
                conn.rollback()
            raise ValueError(f"No se pudo eliminar el usuario: {err.msg}") from err
        except Exception:
            if self.autocommit_transaccion:
                conn.rollback()
            raise
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # INVOCACIÓN DE PROCEDIMIENTOS ALMACENADOS SQL (sp_*) — T1, T2, T7, T8, T9, T10
    # ------------------------------------------------------------------
    @requiere_rol(ROL_ADMIN, ROL_TRABAJADOR)
    def registrar_cliente_validado(
        self,
        nombres: str,
        apellidos: str,
        calle: str | None,
        ciudad: str | None,
        preferencia: str | None,
        id_usuario: int | None = None,
    ) -> int:
        """
        Invoca `CALL sp_registrar_cliente(...)` (T9: O11, O12).
        - Sin parámetro de teléfono (no existe en el modelo físico de 18 tablas).
        - La preferencia debe pertenecer al catálogo oficial `preferencia`.
        """
        assert self.sesion_actual is not None
        nom = (nombres or "").strip()
        ape = (apellidos or "").strip()
        if len(nom) < 2 or len(ape) < 2:
            raise ValueError("Validación Nominal (RN-03): Los nombres y apellidos son obligatorios (mínimo 2 caracteres).")

        uid = self.sesion_actual.id_usuario if not self.sesion_actual.es_admin else (id_usuario or self.sesion_actual.id_usuario)
        pref_limpia = (preferencia or "").strip()

        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            res = cur.callproc(
                "sp_registrar_cliente",
                (
                    nom,
                    ape,
                    (calle or "").strip(),
                    (ciudad or "").strip(),
                    pref_limpia,
                    uid,
                    0,
                ),
            )
            cod_cli = int(res[6])
            self._log(
                "REGISTRO_CLIENTE",
                f"Registrado cliente #{cod_cli}: {nom} {ape} (pref='{pref_limpia or 'ninguna'}').",
                commit=False,
            )
            if self.autocommit_transaccion:
                conn.commit()
            return cod_cli
        except MySQLError as err:
            if self.autocommit_transaccion:
                conn.rollback()
            raise ValueError(err.msg) from err
        finally:
            cur.close()

    @requiere_rol(ROL_ADMIN)
    def eliminar_cliente(self, codigo_cliente: int) -> None:
        """Elimina un cliente del padrón (exclusivo para rol ADMIN, T6)."""
        self.ejecutar("DELETE FROM cliente WHERE codigo_cliente = %s", (codigo_cliente,), commit=False)
        self._log("ELIMINAR_CLIENTE", f"Eliminado cliente #{codigo_cliente}.", commit=False)
        if self.autocommit_transaccion:
            self.commit()

    @requiere_rol(ROL_ADMIN, ROL_TRABAJADOR)
    def registrar_cita_validada(
        self,
        fecha: str,
        hora_inicio: str,
        codigo_servicio: int,
        observaciones: str | None = None,
        id_usuario: int | None = None,
        nombre_cliente: str | None = None,
    ) -> int:
        """
        Invoca `CALL sp_registrar_cita(...)` (T8: O10, O13).
        - Si se indica `nombre_cliente`, antepone `'Cliente: <nombre_cliente>.'` en `observaciones`
          (documentado como límite del modelo físico de 18 tablas donde `cita` no tiene FK a `cliente`).
        - Valida en SQL que la cita no cruce las 24:00 ni se superponga con otra cita activa del mismo usuario.
        """
        assert self.sesion_actual is not None
        uid = self.sesion_actual.id_usuario if not self.sesion_actual.es_admin else (id_usuario or self.sesion_actual.id_usuario)

        obs_base = (observaciones or "").strip()
        cli_limpio = (nombre_cliente or "").strip().rstrip(".")
        if cli_limpio and not obs_base.lower().startswith("cliente:"):
            obs_final = f"Cliente: {cli_limpio}." + (f" {obs_base}" if obs_base else "")
        else:
            obs_final = obs_base

        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            res = cur.callproc(
                "sp_registrar_cita",
                (fecha, hora_inicio, int(codigo_servicio), obs_final[:255], int(uid), 0),
            )
            num_cita = int(res[5])
            self._log(
                "REGISTRO_CITA",
                f"Registrada cita #{num_cita} en {fecha} {hora_inicio} (servicio={codigo_servicio}, usuario={uid}).",
                commit=False,
            )
            if self.autocommit_transaccion:
                conn.commit()
            return num_cita
        except MySQLError as err:
            if self.autocommit_transaccion:
                conn.rollback()
            raise ValueError(err.msg) from err
        finally:
            cur.close()

    @requiere_rol(ROL_ADMIN, ROL_TRABAJADOR)
    def cambiar_estado_cita_validado(self, numero_registro: int, nuevo_estado: str) -> None:
        """
        Invoca `CALL sp_cambiar_estado_cita(p_numero, p_nuevo_estado, p_id_usuario)` (T7: O8, O9).
        - Si el operador es ADMIN, pasa `p_id_usuario = None` (puede gestionar cualquier cita).
        - Si el operador es TRABAJADOR, pasa `p_id_usuario = sesion.id_usuario` (solo puede cambiar sus citas).
        """
        assert self.sesion_actual is not None
        param_usuario = None if self.sesion_actual.es_admin else self.sesion_actual.id_usuario

        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            cur.callproc("sp_cambiar_estado_cita", (int(numero_registro), nuevo_estado.strip(), param_usuario))
            self._log(
                "CAMBIO_ESTADO_CITA",
                f"Cita #{numero_registro} cambiada a '{nuevo_estado}'.",
                commit=False,
            )
            if self.autocommit_transaccion:
                conn.commit()
        except MySQLError as err:
            if self.autocommit_transaccion:
                conn.rollback()
            raise ValueError(err.msg) from err
        finally:
            cur.close()

    @requiere_rol(ROL_ADMIN)
    def eliminar_cita(self, numero_registro: int) -> None:
        """Elimina una cita (exclusivo para rol ADMIN, T6)."""
        self.ejecutar("DELETE FROM cita WHERE numero_registro = %s", (numero_registro,), commit=False)
        self._log("ELIMINAR_CITA", f"Eliminada cita #{numero_registro}.", commit=False)
        if self.autocommit_transaccion:
            self.commit()

    @requiere_rol(ROL_ADMIN, ROL_TRABAJADOR)
    def registrar_venta_atomica(self, codigo_producto: int, cantidad: int) -> tuple[int, str, float]:
        """
        Invoca `CALL sp_registrar_venta(...)` (T1 y T2: O1, O6).
        El stock y el total de la venta son actualizados una única vez por el trigger
        `trg_detalle_venta_descuenta_stock` del esquema de 18 tablas.
        """
        if cantidad <= 0:
            raise ValueError("Validación de Dominio (RN-06): La cantidad a vender debe ser un entero mayor a 0.")

        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            res = cur.callproc("sp_registrar_venta", (int(codigo_producto), int(cantidad), 0, "", 0.0))
            num_venta, nom_prod, total = int(res[2]), str(res[3]), float(res[4])
            self._log(
                "REGISTRO_VENTA",
                f"Venta #{num_venta}: {cantidad} x {nom_prod} (Total S/ {total:.2f}).",
                commit=False,
            )
            if self.autocommit_transaccion:
                conn.commit()
            return num_venta, nom_prod, total
        except MySQLError as err:
            if self.autocommit_transaccion:
                conn.rollback()
            raise ValueError(err.msg) from err
        finally:
            cur.close()

    @requiere_rol(ROL_ADMIN, ROL_TRABAJADOR)
    def registrar_venta_carrito_atomica(self, lineas: list[dict[str, int]]) -> tuple[int, float]:
        """
        Invoca `CALL sp_registrar_venta_carrito(...)` para registrar múltiples productos
        en una sola venta atómica (T10: todo o nada).
        """
        if not lineas:
            raise ValueError("El carrito de venta debe incluir al menos un producto.")
        for item in lineas:
            if int(item.get("cantidad", 0)) <= 0:
                raise ValueError("Validación de Dominio (RN-06): Todas las cantidades del carrito deben ser mayores a 0.")

        payload_json = json.dumps(
            [{"codigo_producto": int(i["codigo_producto"]), "cantidad": int(i["cantidad"])} for i in lineas]
        )
        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            res = cur.callproc("sp_registrar_venta_carrito", (payload_json, 0, 0.0))
            num_venta, total = int(res[1]), float(res[2])
            self._log(
                "REGISTRO_VENTA_CARRITO",
                f"Venta multiproducto #{num_venta} con {len(lineas)} línea(s) (Total S/ {total:.2f}).",
                commit=False,
            )
            if self.autocommit_transaccion:
                conn.commit()
            return num_venta, total
        except MySQLError as err:
            if self.autocommit_transaccion:
                conn.rollback()
            raise ValueError(err.msg) from err
        finally:
            cur.close()

    @requiere_rol(ROL_ADMIN, ROL_TRABAJADOR)
    def descontar_botella_cabina_validada(self, codigo_producto: int) -> str:
        """Invoca `CALL sp_descontar_botella_cabina(...)` (consumo interno en cabina estética, T1)."""
        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            res = cur.callproc("sp_descontar_botella_cabina", (int(codigo_producto), "", 0))
            nom_prod, stock_rest = str(res[1]), int(res[2])
            self._log(
                "CONSUMO_CABINA",
                f"Descontada 1 unidad en cabina de '{nom_prod}' (stock restante={stock_rest}).",
                commit=False,
            )
            if self.autocommit_transaccion:
                conn.commit()
            return nom_prod
        except MySQLError as err:
            if self.autocommit_transaccion:
                conn.rollback()
            raise ValueError(err.msg) from err
        finally:
            cur.close()

    @requiere_rol(ROL_ADMIN)
    def registrar_pedido_compra_atomico(
        self,
        id_usuario_admin: int | None,
        codigo_proveedor: int,
        codigo_producto: int,
        cantidad: int,
        costo_unitario: float,
    ) -> int:
        """
        Invoca `CALL sp_registrar_pedido_compra(...)` (T1, T2, T6).
        El incremento de stock lo realiza exclusivamente el trigger `trg_detalle_pedido_aumenta_stock`.
        """
        assert self.sesion_actual is not None
        if cantidad <= 0:
            raise ValueError("Validación de Lote (RN-06): La cantidad comprada debe ser un entero mayor a 0.")
        if costo_unitario <= 0:
            raise ValueError("Validación de Costo (RN-09): El costo unitario de compra debe ser mayor a S/ 0.00.")

        uid_admin = id_usuario_admin if id_usuario_admin is not None else self.sesion_actual.id_usuario
        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            res = cur.callproc(
                "sp_registrar_pedido_compra",
                (int(uid_admin), int(codigo_proveedor), int(codigo_producto), int(cantidad), round(costo_unitario, 2), 0),
            )
            id_ped = int(res[5])
            self._log(
                "REGISTRO_PEDIDO_COMPRA",
                f"Pedido #{id_ped}: +{cantidad} und. del producto #{codigo_producto} (proveedor #{codigo_proveedor}).",
                commit=False,
            )
            if self.autocommit_transaccion:
                conn.commit()
            return id_ped
        except MySQLError as err:
            if self.autocommit_transaccion:
                conn.rollback()
            raise ValueError(err.msg) from err
        finally:
            cur.close()

    @requiere_rol(ROL_ADMIN)
    def agregar_producto_catalogo(
        self,
        nombre: str,
        descripcion: str,
        precio_unitario: float,
        stock_inicial: int,
        codigo_almacen: int | None = None,
    ) -> int:
        """Alta de producto en el catálogo (exclusivo para rol ADMIN, T6)."""
        nom = (nombre or "").strip()
        if not nom:
            raise ValueError("El nombre del producto es obligatorio.")
        if precio_unitario <= 0:
            raise ValueError("El precio unitario debe ser mayor a S/ 0.00 (RN-09).")
        if stock_inicial < 0:
            raise ValueError("El stock inicial no puede ser negativo (RN-08).")

        desc = (descripcion or "").strip() or None
        if codigo_almacen is None:
            filas_alm = self.consultar("SELECT codigo_almacen FROM almacen ORDER BY codigo_almacen LIMIT 1")
            if not filas_alm:
                raise ValueError("No existe ningún almacén registrado en la base de datos.")
            codigo_almacen = int(filas_alm[0]["codigo_almacen"])

        cod_prod = self.ejecutar(
            "INSERT INTO producto (nombre, descripcion, precio_unitario, stock, codigo_almacen) VALUES (%s, %s, %s, %s, %s)",
            (nom, desc, round(precio_unitario, 2), int(stock_inicial), int(codigo_almacen)),
            commit=False,
        )
        self._log("ALTA_PRODUCTO", f"Creado producto #{cod_prod}: {nom} (S/ {precio_unitario:.2f}).", commit=False)
        if self.autocommit_transaccion:
            self.commit()
        return cod_prod

    @requiere_rol(ROL_ADMIN)
    def actualizar_precio_producto(self, codigo_producto: int, nuevo_precio: float) -> None:
        """Actualiza el precio unitario de un producto (exclusivo para rol ADMIN, T6)."""
        if nuevo_precio <= 0:
            raise ValueError("El precio unitario debe ser estrictamente mayor a S/ 0.00 (RN-09).")
        self.ejecutar(
            "UPDATE producto SET precio_unitario = %s WHERE codigo_producto = %s",
            (round(nuevo_precio, 2), int(codigo_producto)),
            commit=False,
        )
        self._log(
            "ACTUALIZAR_PRECIO_PRODUCTO",
            f"Producto #{codigo_producto} actualizado a S/ {nuevo_precio:.2f}.",
            commit=False,
        )
        if self.autocommit_transaccion:
            self.commit()

    def listar_procedimientos_almacenados(self) -> list[dict]:
        """Consulta en `information_schema.ROUTINES` los procedimientos almacenados activos."""
        return self.consultar(
            """
            SELECT ROUTINE_NAME AS nombre,
                   ROUTINE_TYPE AS tipo,
                   CREATED AS creado,
                   LAST_ALTERED AS modificado
              FROM information_schema.ROUTINES
             WHERE ROUTINE_SCHEMA = %s AND ROUTINE_TYPE = 'PROCEDURE'
             ORDER BY ROUTINE_NAME
            """,
            (self.nombre_bd,),
        )

    def obtener_ddl_procedimiento(self, nombre_sp: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_]+", nombre_sp or ""):
            raise ValueError("Nombre de procedimiento inválido.")
        filas = self.consultar(f"SHOW CREATE PROCEDURE `{nombre_sp}`")
        if filas:
            return str(filas[0].get("Create Procedure") or "")
        return ""

