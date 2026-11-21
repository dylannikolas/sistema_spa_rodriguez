# -*- coding: utf-8 -*-
"""
Módulo de seguridad criptográfica y política de contraseñas (T3: O2, O3, O4).
Implementa PBKDF2-HMAC-SHA256 (>= 200 000 iteraciones) con sal única por usuario
y comparación en tiempo constante mediante hmac.compare_digest.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets

ITERACIONES_PBKDF2: int = 210_000
LONGITUD_SAL_BYTES: int = 16
LONGITUD_MIN_CLAVE: int = 8

CLAVES_PROHIBIDAS: frozenset[str] = frozenset({
    "spa123",
    "admin123",
    "12345678",
    "password",
    "password1",
    "qwerty123",
    "rodriguez123",
})


def generar_hash_contrasena(
    contrasena: str,
    salt: bytes | None = None,
    iteraciones: int = ITERACIONES_PBKDF2,
) -> tuple[str, str, int]:
    """
    Deriva el hash PBKDF2-HMAC-SHA256 de una contraseña.
    Retorna (hash_hex, salt_hex, iteraciones).
    """
    if not contrasena:
        raise ValueError("La contraseña no puede estar vacía.")
    if iteraciones < 200_000:
        raise ValueError("El número de iteraciones PBKDF2 debe ser al menos 200 000.")
    sal_bytes = salt if salt is not None else os.urandom(LONGITUD_SAL_BYTES)
    derivado = hashlib.pbkdf2_hmac(
        "sha256",
        contrasena.encode("utf-8"),
        sal_bytes,
        iteraciones,
    )
    return derivado.hex(), sal_bytes.hex(), iteraciones


def verificar_contrasena(
    contrasena_plana: str,
    hash_esperado_hex: str,
    salt_hex: str,
    iteraciones: int,
) -> bool:
    """Compara una contraseña con su hash PBKDF2 en tiempo constante."""
    if not contrasena_plana or not hash_esperado_hex or not salt_hex or iteraciones <= 0:
        return False
    try:
        sal_bytes = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    derivado = hashlib.pbkdf2_hmac(
        "sha256",
        contrasena_plana.encode("utf-8"),
        sal_bytes,
        int(iteraciones),
    )
    return hmac.compare_digest(derivado.hex(), hash_esperado_hex)


def validar_politica_contrasena(nueva_clave: str, username: str = "") -> None:
    """
    Valida que la contraseña cumpla la política de seguridad (T3):
    - Mínimo 8 caracteres.
    - Contiene al menos una letra y al menos un número.
    - Es distinta del nombre de usuario (username).
    - No pertenece a la lista de contraseñas prohibidas por defecto.
    """
    if not nueva_clave or len(nueva_clave) < LONGITUD_MIN_CLAVE:
        raise ValueError(f"La contraseña debe tener al menos {LONGITUD_MIN_CLAVE} caracteres.")
    if not re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]", nueva_clave):
        raise ValueError("La contraseña debe incluir al menos una letra.")
    if not re.search(r"[0-9]", nueva_clave):
        raise ValueError("La contraseña debe incluir al menos un número.")
    limpia = nueva_clave.strip().lower()
    if limpia in CLAVES_PROHIBIDAS:
        raise ValueError("La contraseña elegida es demasiado común o no está permitida.")
    usr_limpio = (username or "").strip().lower()
    if usr_limpio and (limpia == usr_limpio or usr_limpio in limpia):
        raise ValueError("La contraseña no puede ser igual ni contener el nombre de usuario.")


def generar_clave_temporal() -> str:
    """
    Genera una contraseña temporal aleatoria criptográficamente segura
    que cumple la política (letras + números, >= 12 caracteres).
    """
    while True:
        base = secrets.token_urlsafe(9)
        digito = str(secrets.randbelow(9) + 1)
        letra = secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        candidata = f"{letra}{base}{digito}"
        try:
            validar_politica_contrasena(candidata)
            return candidata
        except ValueError:
            continue
