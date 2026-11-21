# -*- coding: utf-8 -*-
"""
Módulo de autenticación segura, bloqueo por intentos, gestión de roles explícitos
y bitácora persistente en el esquema separado `spa_rodriguez_app` (T3, T4, T6, T11).
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata
from mysql.connector import Error as MySQLError

from db import ConexionBaseDatos
from permisos import ROL_ADMIN, ROL_TRABAJADOR, ROLES_VALIDOS, SesionUsuario
from seguridad import (
    generar_clave_temporal,
    generar_hash_contrasena,
    validar_politica_contrasena,
    verificar_contrasena,
)

MAX_INTENTOS_FALLIDOS = 5
MINUTOS_BLOQUEO = 5
MSG_LOGIN_GENERICO = "Usuario o contraseña incorrectos."


def sugerir_username(nombre: str, id_usuario: int | None = None) -> str:
    """Genera un identificador de login limpio a partir del nombre del usuario."""
    limpio = "".join(
        c for c in unicodedata.normalize("NFD", (nombre or "").strip().lower())
        if unicodedata.category(c) != "Mn"
    )
    partes = [re.sub(r"[^a-z0-9]", "", p) for p in limpio.split() if p]
    if len(partes) >= 2:
        base = f"{partes[0]}.{partes[1]}"
    elif partes:
        base = partes[0]
    else:
        base = f"usuario{id_usuario or ''}"
    return base[:45]


class GestorAutenticacion:
    """Gestiona credenciales PBKDF2, sesiones y bitácora sobre `spa_rodriguez_app`."""

    def __init__(self, conexion: ConexionBaseDatos):
        self.db = conexion

    @property
    def esquema_auth(self) -> str:
        return self.db.nombre_bd_auth

    @property
    def esquema_datos(self) -> str:
        return self.db.nombre_bd

    def verificar_esquema_auth_instalado(self) -> bool:
        """Comprueba en information_schema si existen `credencial` y `bitacora` en `spa_rodriguez_app`."""
        filas = self.db.consultar(
            """
            SELECT TABLE_NAME AS tabla
              FROM information_schema.tables
             WHERE table_schema = %s AND table_name IN ('credencial', 'bitacora')
            """,
            (self.esquema_auth,),
        )
        tablas = {str(f.get("tabla") or f.get("TABLE_NAME") or f.get("table_name", "")).lower() for f in filas}
        return {"credencial", "bitacora"}.issubset(tablas)

    def registrar_bitacora(
        self,
        accion: str,
        detalle: str,
        id_usuario: int | None = None,
        username: str | None = None,
        commit: bool | None = None,
    ) -> None:
        """Guarda un evento persistente en `spa_rodriguez_app.bitacora` (T11)."""
        sql = f"""
            INSERT INTO `{self.esquema_auth}`.`bitacora`
                (id_usuario, username, accion, detalle, fecha_hora)
            VALUES (%s, %s, %s, %s, NOW())
        """
        self.db.ejecutar(sql, (id_usuario, username, accion[:80], detalle[:500]), commit=commit)

    def consultar_bitacora(self, limite: int = 200, filtro: str = "") -> list[dict]:
        """Devuelve los registros más recientes de la bitácora persistente."""
        q = (filtro or "").strip()
        if q:
            patron = f"%{q}%"
            sql = f"""
                SELECT id_bitacora, fecha_hora, id_usuario, COALESCE(username, '—') AS username,
                       accion, detalle
                  FROM `{self.esquema_auth}`.`bitacora`
                 WHERE username LIKE %s OR accion LIKE %s OR detalle LIKE %s
                 ORDER BY id_bitacora DESC
                 LIMIT %s
            """
            return self.db.consultar(sql, (patron, patron, patron, int(limite)))

        sql = f"""
            SELECT id_bitacora, fecha_hora, id_usuario, COALESCE(username, '—') AS username,
                   accion, detalle
              FROM `{self.esquema_auth}`.`bitacora`
             ORDER BY id_bitacora DESC
             LIMIT %s
        """
        return self.db.consultar(sql, (int(limite),))

    def autenticar(self, username: str, contrasena: str) -> SesionUsuario:
        """
        Autentica a un usuario consultando exclusivamente por `username` (T3: O2, O3, O4):
        - No acepta ID numérico ni nombre completo.
        - No carga la lista completa de usuarios.
        - Rechaza cuentas inactivas o bloqueadas temporalmente.
        - Aplica PBKDF2-HMAC-SHA256 con comparación en tiempo constante.
        - Bloquea 5 minutos tras 5 intentos fallidos consecutivos.
        """
        usr = (username or "").strip().lower()
        pwd = contrasena or ""
        if not usr or not pwd:
            raise ValueError(MSG_LOGIN_GENERICO)

        # No permitir login por ID numérico ni por nombre con espacios
        if usr.isdigit() or " " in usr:
            self.registrar_bitacora(
                "LOGIN_RECHAZADO",
                f"Intento de login con identificador no permitido ({usr!r}).",
                username=usr,
            )
            raise ValueError(MSG_LOGIN_GENERICO)

        sql = f"""
            SELECT c.id_usuario,
                   c.username,
                   c.rol,
                   c.hash_clave,
                   c.salt,
                   c.iteraciones,
                   c.activo,
                   c.debe_cambiar,
                   c.intentos_fallidos,
                   c.bloqueado_hasta,
                   NOW() AS ahora_servidor,
                   COALESCE(u.nombre, c.username) AS nombre,
                   (SELECT GROUP_CONCAT(DISTINCT esp.nombre_especialidad SEPARATOR ', ')
                      FROM `{self.esquema_datos}`.`empleado` e
                      JOIN `{self.esquema_datos}`.`especialidad` esp
                        ON esp.id_especialidad = e.id_especialidad
                     WHERE e.id_usuario = c.id_usuario) AS especialidad
              FROM `{self.esquema_auth}`.`credencial` c
              LEFT JOIN `{self.esquema_datos}`.`usuario` u
                ON u.id_usuario = c.id_usuario
             WHERE c.username = %s
             LIMIT 1
        """
        filas = self.db.consultar(sql, (usr,))
        if not filas:
            self.registrar_bitacora(
                "LOGIN_FALLIDO",
                f"Usuario inexistente ({usr}).",
                username=usr,
            )
            raise ValueError(MSG_LOGIN_GENERICO)

        cred = filas[0]
        uid = int(cred["id_usuario"])

        if not bool(cred["activo"]):
            self.registrar_bitacora(
                "LOGIN_CUENTA_INACTIVA",
                "Intento de acceso sobre cuenta desactivada.",
                id_usuario=uid,
                username=usr,
            )
            raise ValueError("Esta cuenta se encuentra desactivada. Contacte al administrador.")

        bloqueado_hasta: dt.datetime | None = cred.get("bloqueado_hasta")
        ahora_srv: dt.datetime = cred.get("ahora_servidor") or dt.datetime.now()
        if bloqueado_hasta is not None and bloqueado_hasta > ahora_srv:
            segundos = max(1, int((bloqueado_hasta - ahora_srv).total_seconds()))
            minutos_rest = (segundos + 59) // 60
            self.registrar_bitacora(
                "LOGIN_CUENTA_BLOQUEADA",
                f"Intento durante bloqueo activo ({minutos_rest} min restantes).",
                id_usuario=uid,
                username=usr,
            )
            raise ValueError(
                f"Cuenta bloqueada temporalmente por intentos fallidos. Intente nuevamente en {minutos_rest} minuto(s)."
            )

        es_valida = verificar_contrasena(
            pwd,
            str(cred["hash_clave"]),
            str(cred["salt"]),
            int(cred["iteraciones"]),
        )
        if not es_valida:
            nuevos_intentos = int(cred["intentos_fallidos"] or 0) + 1
            if nuevos_intentos >= MAX_INTENTOS_FALLIDOS:
                self.db.ejecutar(
                    f"""
                    UPDATE `{self.esquema_auth}`.`credencial`
                       SET intentos_fallidos = %s,
                           bloqueado_hasta = DATE_ADD(NOW(), INTERVAL %s MINUTE)
                     WHERE id_usuario = %s
                    """,
                    (nuevos_intentos, MINUTOS_BLOQUEO, uid),
                )
                self.registrar_bitacora(
                    "BLOQUEO_CUENTA",
                    f"Cuenta bloqueada por {MINUTOS_BLOQUEO} minutos tras {nuevos_intentos} intentos fallidos.",
                    id_usuario=uid,
                    username=usr,
                )
            else:
                self.db.ejecutar(
                    f"""
                    UPDATE `{self.esquema_auth}`.`credencial`
                       SET intentos_fallidos = %s
                     WHERE id_usuario = %s
                    """,
                    (nuevos_intentos, uid),
                )
                self.registrar_bitacora(
                    "LOGIN_FALLIDO",
                    f"Contraseña incorrecta (intento {nuevos_intentos}/{MAX_INTENTOS_FALLIDOS}).",
                    id_usuario=uid,
                    username=usr,
                )
            raise ValueError(MSG_LOGIN_GENERICO)

        # Login exitoso: restablecer contador de intentos y registrar último acceso
        self.db.ejecutar(
            f"""
            UPDATE `{self.esquema_auth}`.`credencial`
               SET intentos_fallidos = 0,
                   bloqueado_hasta = NULL,
                   ultimo_acceso = NOW()
             WHERE id_usuario = %s
            """,
            (uid,),
        )
        rol_explicito = str(cred["rol"]).upper()
        if rol_explicito not in ROLES_VALIDOS:
            rol_explicito = ROL_TRABAJADOR

        debe_cambiar = bool(cred["debe_cambiar"])
        self.registrar_bitacora(
            "LOGIN_EXITOSO",
            f"Inicio de sesión exitoso con rol {rol_explicito}"
            + (" (requiere cambio de clave temporal)." if debe_cambiar else "."),
            id_usuario=uid,
            username=usr,
        )

        esp_default = (
            "Administración / Recepción / Almacén"
            if rol_explicito == ROL_ADMIN
            else "Especialista de Cabina"
        )
        return SesionUsuario(
            id_usuario=uid,
            username=str(cred["username"]),
            nombre=str(cred["nombre"]),
            rol=rol_explicito,
            debe_cambiar=debe_cambiar,
            especialidad=str(cred.get("especialidad") or esp_default),
        )

    def cambiar_contrasena(self, id_usuario: int, clave_actual: str, clave_nueva: str) -> None:
        """
        Permite al usuario cambiar su contraseña verificando primero su clave actual
        y exigiendo el cumplimiento de la política de seguridad (T3: O4).
        """
        filas = self.db.consultar(
            f"""
            SELECT id_usuario, username, hash_clave, salt, iteraciones
              FROM `{self.esquema_auth}`.`credencial`
             WHERE id_usuario = %s
            """,
            (id_usuario,),
        )
        if not filas:
            raise ValueError("No se encontró la credencial del usuario.")

        cred = filas[0]
        usr = str(cred["username"])
        if not verificar_contrasena(
            clave_actual or "",
            str(cred["hash_clave"]),
            str(cred["salt"]),
            int(cred["iteraciones"]),
        ):
            self.registrar_bitacora(
                "CAMBIO_CLAVE_FALLIDO",
                "La contraseña actual ingresada no coincide.",
                id_usuario=id_usuario,
                username=usr,
            )
            raise ValueError("La contraseña actual ingresada es incorrecta.")

        if clave_actual == clave_nueva:
            raise ValueError("La nueva contraseña debe ser diferente de la contraseña actual.")

        validar_politica_contrasena(clave_nueva, usr)
        nuevo_hash, nuevo_salt, iters = generar_hash_contrasena(clave_nueva)

        self.db.ejecutar(
            f"""
            UPDATE `{self.esquema_auth}`.`credencial`
               SET hash_clave = %s,
                   salt = %s,
                   iteraciones = %s,
                   debe_cambiar = 0,
                   intentos_fallidos = 0,
                   bloqueado_hasta = NULL
             WHERE id_usuario = %s
            """,
            (nuevo_hash, nuevo_salt, iters, id_usuario),
        )
        self.registrar_bitacora(
            "CAMBIO_CLAVE_EXITOSO",
            "El usuario actualizó su contraseña personal cumpliendo la política de seguridad.",
            id_usuario=id_usuario,
            username=usr,
        )

    def restablecer_clave_temporal(
        self,
        id_usuario_objetivo: int,
        sesion_admin: SesionUsuario,
    ) -> str:
        """
        Genera una nueva contraseña temporal aleatoria para un usuario y marca `debe_cambiar = 1`.
        Retorna la contraseña temporal una sola vez para que el administrador la entregue.
        """
        if sesion_admin.rol != ROL_ADMIN:
            raise PermissionError("Solo un Administrador puede restablecer contraseñas.")

        filas = self.db.consultar(
            f"SELECT username FROM `{self.esquema_auth}`.`credencial` WHERE id_usuario = %s",
            (id_usuario_objetivo,),
        )
        if not filas:
            raise ValueError("El usuario indicado no posee credencial registrada.")

        usr_obj = str(filas[0]["username"])
        clave_temp = generar_clave_temporal()
        hash_hex, salt_hex, iters = generar_hash_contrasena(clave_temp)

        self.db.ejecutar(
            f"""
            UPDATE `{self.esquema_auth}`.`credencial`
               SET hash_clave = %s,
                   salt = %s,
                   iteraciones = %s,
                   debe_cambiar = 1,
                   intentos_fallidos = 0,
                   bloqueado_hasta = NULL
             WHERE id_usuario = %s
            """,
            (hash_hex, salt_hex, iters, id_usuario_objetivo),
        )
        self.registrar_bitacora(
            "RESET_CLAVE_TEMPORAL",
            f"Contraseña restablecida temporalmente para el usuario '{usr_obj}' (ID {id_usuario_objetivo}).",
            id_usuario=sesion_admin.id_usuario,
            username=sesion_admin.username,
        )
        return clave_temp

