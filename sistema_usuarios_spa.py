# -*- coding: utf-8 -*-
"""
Punto de entrada principal del Portal Operativo de Usuarios — Salón Spa Rodríguez.
Arquitectura modularizada (T12):
- config.py     : Configuración desde .env y diccionario centralizado de reglas (RN).
- db.py         : Conexión MySQL 8.0 sin DDL automático al iniciar.
- seguridad.py  : Hash PBKDF2-HMAC-SHA256 (>= 200 000 iteraciones), sal única y política de claves.
- permisos.py   : Roles explícitos (ADMIN / TRABAJADOR) y decorador @requiere_rol.
- auth.py       : Autenticación segura, bloqueo por intentos y bitácora en `spa_rodriguez_app`.
- servicios.py  : Acceso a datos y llamadas a Procedimientos Almacenados SQL (`callproc`).
- ui/           : Interfaz gráfica Tkinter separada de la lógica de datos.
"""
from __future__ import annotations

from tkinter import messagebox

from auth import GestorAutenticacion, sugerir_username
from config import (
    PROCEDIMIENTOS_REQUERIDOS,
    RN,
    TABLAS_MODELO_18,
    leer_env_archivo,
    obtener_parametros_conexion,
)
from db import ConexionBaseDatos
from permisos import ROL_ADMIN, ROL_TRABAJADOR, ROLES_VALIDOS, SesionUsuario, requiere_rol, verificar_rol
from seguridad import (
    ITERACIONES_PBKDF2,
    generar_clave_temporal,
    generar_hash_contrasena,
    validar_politica_contrasena,
    verificar_contrasena,
)
from servicios import GestorBaseDatos
from ui import PortalUsuariosSpaApp

__all__ = [
    "ConexionBaseDatos",
    "GestorAutenticacion",
    "GestorBaseDatos",
    "ITERACIONES_PBKDF2",
    "PROCEDIMIENTOS_REQUERIDOS",
    "PortalUsuariosSpaApp",
    "RN",
    "ROLES_VALIDOS",
    "ROL_ADMIN",
    "ROL_TRABAJADOR",
    "SesionUsuario",
    "TABLAS_MODELO_18",
    "generar_clave_temporal",
    "generar_hash_contrasena",
    "leer_env_archivo",
    "obtener_parametros_conexion",
    "requiere_rol",
    "sugerir_username",
    "validar_politica_contrasena",
    "verificar_contrasena",
    "verificar_rol",
]


def main() -> None:
    params = obtener_parametros_conexion()
    gestor = GestorBaseDatos(params=params)
    try:
        gestor.conectar()
    except Exception as err:
        messagebox.showerror("Error de Conexión a MySQL", str(err))
        return

    app = PortalUsuariosSpaApp(gestor)
    app.mainloop()


if __name__ == "__main__":
    main()
