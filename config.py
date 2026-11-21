# -*- coding: utf-8 -*-
"""
Módulo de configuración centralizada — Salón Spa Rodríguez.
Lee parámetros exclusivamente desde variables de entorno o archivo .env local,
sin rutas personales ni secretos fijos en el código fuente.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Diccionario centralizado de Reglas de Negocio (Sección 1.5 de las indicaciones).
# Permite actualizar la numeración o descripción en un único lugar.
RN: dict[str, str] = {
    "RN-01": "Trazabilidad obligatoria del usuario responsable en registros operativos",
    "RN-02": "Control de acceso basado en roles explícitos (ADMIN / TRABAJADOR)",
    "RN-03": "Integridad de datos de clientes y preferencias exclusivas del catálogo oficial (3FN)",
    "RN-04": "Ciclo de vida de la cita (Pendiente -> Confirmada/Cancelada; Confirmada -> Atendida/Cancelada)",
    "RN-05": "Cálculo automático de hora de fin según duración del servicio y control horario (< 24:00, sin solapamiento)",
    "RN-06": "Cantidades estrictamente positivas (> 0) en ventas y pedidos de compra",
    "RN-07": "Control automático de existencias mediante triggers (ventas/pedidos) y descuento en cabina",
    "RN-08": "Prohibición de vender o descontar por encima del stock disponible (stock >= 0)",
    "RN-09": "Precios unitarios y costos estrictamente positivos (> S/ 0.00)",
}

TABLAS_MODELO_18: tuple[str, ...] = (
    "usuario",
    "especialidad",
    "estado_cita",
    "preferencia",
    "proveedor",
    "servicio",
    "venta",
    "almacen",
    "empleado",
    "cliente",
    "cliente_preferencia",
    "producto",
    "cita",
    "cita_servicio",
    "servicio_producto",
    "pedido_compra",
    "detalle_pedido",
    "detalle_venta",
)

PROCEDIMIENTOS_REQUERIDOS: tuple[str, ...] = (
    "sp_registrar_venta",
    "sp_registrar_venta_carrito",
    "sp_registrar_pedido_compra",
    "sp_descontar_botella_cabina",
    "sp_cambiar_estado_cita",
    "sp_registrar_cita",
    "sp_registrar_cliente",
)


def leer_env_archivo(ruta_env: Path) -> dict[str, str]:
    """Lee un archivo .env con formato CLAVE=VALOR."""
    datos: dict[str, str] = {}
    if not ruta_env.exists():
        return datos
    for linea in ruta_env.read_text(encoding="utf-8", errors="replace").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        datos[clave.strip()] = valor.strip().strip('"').strip("'")
    return datos


def obtener_parametros_conexion(
    nombre_bd: str | None = None,
    ruta_env: Path | None = None,
) -> dict[str, str | int]:
    """Obtiene los parámetros de conexión desde .env o variables de entorno."""
    candidatos = [ruta_env] if ruta_env else [BASE_DIR / ".env", BASE_DIR / "etl_spa" / ".env"]
    env_vars: dict[str, str] = {}
    for candidato in candidatos:
        if candidato and candidato.exists():
            env_vars = leer_env_archivo(candidato)
            break

    def _get(clave: str, defecto: str = "") -> str:
        return os.environ.get(clave, env_vars.get(clave, defecto))

    puerto_str = _get("DB_PORT", "3306")
    try:
        puerto = int(puerto_str)
    except ValueError as err:
        raise ValueError(f"DB_PORT inválido en la configuración: {puerto_str!r}") from err

    bd_principal = nombre_bd or _get("DB_NAME", "spa_rodriguez")
    bd_auth = nombre_bd if nombre_bd else (_get("DB_AUTH_NAME", bd_principal) or bd_principal)
    return {
        "host": _get("DB_HOST", "localhost"),
        "port": puerto,
        "user": _get("DB_USER", "root"),
        "password": _get("DB_PASSWORD", ""),
        "database": bd_principal,
        "auth_database": bd_auth,
    }

