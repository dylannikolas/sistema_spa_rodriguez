# -*- coding: utf-8 -*-
"""
Módulo de conexión a la base de datos MySQL 8.0 (T5: O7).
Reglas estrictas:
- No ejecuta sentencias DDL sobre tablas, disparadores ni rutinas al conectarse.
- Se conecta únicamente a la base configurada en .env (DB_NAME), sin elegir bases al azar.
- Solo verifica la presencia de las tablas del modelo y los procedimientos almacenados en information_schema.
"""
from __future__ import annotations

import mysql.connector
from mysql.connector import Error as MySQLError

from config import PROCEDIMIENTOS_REQUERIDOS, TABLAS_MODELO_18, obtener_parametros_conexion


class ConexionBaseDatos:
    """Gestiona la conexión transaccional al servidor MySQL 8.0 sin modificar el esquema."""

    def __init__(self, params: dict[str, str | int] | None = None, autocommit_transaccion: bool = True):
        self.params = dict(params) if params is not None else obtener_parametros_conexion()
        self.autocommit_transaccion = autocommit_transaccion
        self.conn: mysql.connector.MySQLConnection | None = None
        self.tablas_disponibles: set[str] = set()
        self.procedimientos_faltantes: list[str] = []

    @property
    def nombre_bd(self) -> str:
        return str(self.params.get("database", "spa_rodriguez"))

    @property
    def nombre_bd_auth(self) -> str:
        return str(self.params.get("auth_database", "spa_rodriguez_app"))

    def conectar(self, nombre_bd: str | None = None) -> None:
        """
        Abre la conexión hacia la base de datos configurada y verifica (en modo solo lectura)
        qué tablas y procedimientos almacenados están disponibles.
        """
        if self.conn is not None and self.conn.is_connected():
            self.conn.close()

        objetivo = (nombre_bd or self.nombre_bd).strip()
        if not objetivo:
            raise ValueError("El nombre de la base de datos (DB_NAME) no está configurado en .env.")

        self.params["database"] = objetivo
        try:
            self.conn = mysql.connector.connect(
                host=str(self.params["host"]),
                port=int(self.params["port"]),
                user=str(self.params["user"]),
                password=str(self.params["password"]),
                database=objetivo,
                charset="utf8mb4",
                use_unicode=True,
                autocommit=False,
                connection_timeout=10,
            )
        except MySQLError as err:
            raise RuntimeError(
                f"No se pudo conectar a la base de datos configurada '{objetivo}': {err.msg}. "
                "Verifique su archivo .env y que la base exista."
            ) from err

        self.inspeccionar_esquema()

    def asegurar_conexion(self) -> mysql.connector.MySQLConnection:
        if self.conn is None or not self.conn.is_connected():
            self.conectar(self.nombre_bd)
        assert self.conn is not None
        return self.conn

    def cerrar(self) -> None:
        if self.conn is not None and self.conn.is_connected():
            self.conn.close()
        self.conn = None

    def inspeccionar_esquema(self) -> None:
        """
        Verifica en modo de solo lectura las tablas y procedimientos instalados.
        Nunca ejecuta DDL (ALTER, DROP ni CREATE).
        """
        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT table_name
                  FROM information_schema.tables
                 WHERE table_schema = %s AND table_type = 'BASE TABLE'
                """,
                (self.nombre_bd,),
            )
            self.tablas_disponibles = {str(r[0]).lower() for r in cur.fetchall()}
            self.procedimientos_faltantes = self.verificar_procedimientos()
            if self.autocommit_transaccion:
                conn.commit()
        finally:
            cur.close()

    def verificar_procedimientos(self) -> list[str]:
        """Devuelve la lista de procedimientos almacenados requeridos que faltan en la base activa."""
        conn = self.asegurar_conexion()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT routine_name
                  FROM information_schema.routines
                 WHERE routine_schema = %s AND routine_type = 'PROCEDURE'
                """,
                (self.nombre_bd,),
            )
            instalados = {str(r[0]).lower() for r in cur.fetchall()}
            if self.autocommit_transaccion:
                conn.commit()
            return [sp for sp in PROCEDIMIENTOS_REQUERIDOS if sp.lower() not in instalados]
        finally:
            cur.close()

    def verificar_tablas_modelo_18(self) -> list[str]:
        """Devuelve las tablas del modelo físico de 18 tablas que faltan en la base activa."""
        return [t for t in TABLAS_MODELO_18 if t not in self.tablas_disponibles]

    def consultar(self, sql: str, params: tuple | list | None = None) -> list[dict]:
        conn = self.asegurar_conexion()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(sql, params or ())
            filas = cur.fetchall()
            if self.autocommit_transaccion:
                conn.commit()
            return filas
        finally:
            cur.close()

    def ejecutar(self, sql: str, params: tuple | list | None = None, commit: bool | None = None) -> int:
        conn = self.asegurar_conexion()
        debe_confirmar = self.autocommit_transaccion if commit is None else commit
        cur = conn.cursor()
        try:
            cur.execute(sql, params or ())
            last_id = cur.lastrowid or 0
            if debe_confirmar:
                conn.commit()
            return int(last_id)
        except MySQLError:
            if debe_confirmar:
                conn.rollback()
            raise
        finally:
            cur.close()

    def commit(self) -> None:
        if self.conn is not None and self.conn.is_connected():
            self.conn.commit()

    def rollback(self) -> None:
        if self.conn is not None and self.conn.is_connected():
            self.conn.rollback()
