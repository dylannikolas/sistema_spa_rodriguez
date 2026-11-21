# -*- coding: utf-8 -*-
"""
Módulo de roles explícitos y autorización en la capa de datos (T4 y T6).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Callable, TypeVar, Any

ROL_ADMIN = "ADMIN"
ROL_TRABAJADOR = "TRABAJADOR"
ROLES_VALIDOS = (ROL_ADMIN, ROL_TRABAJADOR)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class SesionUsuario:
    """Representa la sesión autenticada de un operador del sistema."""
    id_usuario: int
    username: str
    nombre: str
    rol: str
    debe_cambiar: bool = False
    especialidad: str = ""

    @property
    def es_admin(self) -> bool:
        return self.rol == ROL_ADMIN

    @property
    def rol_etiqueta(self) -> str:
        return "Administrador" if self.rol == ROL_ADMIN else "Trabajador"


def verificar_rol(sesion: SesionUsuario | None, *roles_permitidos: str) -> SesionUsuario:
    """Verifica que exista una sesión activa y que su rol esté autorizado."""
    if sesion is None:
        raise PermissionError("Acceso denegado: debe iniciar sesión antes de ejecutar esta operación.")
    if sesion.debe_cambiar:
        raise PermissionError("Acceso denegado: debe cambiar su contraseña temporal antes de operar.")
    if roles_permitidos and sesion.rol not in roles_permitidos:
        roles_txt = ", ".join(roles_permitidos)
        raise PermissionError(
            f"Acceso denegado (RN-02): esta operación requiere rol [{roles_txt}] y su rol actual es [{sesion.rol}]."
        )
    return sesion


def requiere_rol(*roles_permitidos: str) -> Callable[[F], F]:
    """
    Decorador para métodos de la capa de datos/servicios que exige
    que `self.sesion_actual` tenga uno de los roles permitidos (T6).
    """
    def decorador(func: F) -> F:
        @wraps(func)
        def envoltura(self: Any, *args: Any, **kwargs: Any) -> Any:
            sesion = getattr(self, "sesion_actual", None)
            verificar_rol(sesion, *roles_permitidos)
            return func(self, *args, **kwargs)
        return envoltura  # type: ignore[return-value]
    return decorador

