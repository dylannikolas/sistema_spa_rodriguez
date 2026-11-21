# -*- coding: utf-8 -*-
"""
Script de instalación única del esquema de seguridad y bitácora `spa_rodriguez_app` (T3, T4, T5, T11).
Crea las tablas `credencial` y `bitacora` en un esquema separado (para que el ETL no borre
usuarios ni contraseñas al truncar las 18 tablas del modelo físico) y genera una contraseña
temporal aleatoria única por usuario usando PBKDF2-HMAC-SHA256 (>= 200 000 iteraciones).

Uso:
    python setup_auth.py [--db spa_rodriguez] [--regenerar]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import mysql.connector

from auth import sugerir_username
from config import BASE_DIR, obtener_parametros_conexion
from permisos import ROL_ADMIN, ROL_TRABAJADOR
from seguridad import generar_clave_temporal, generar_hash_contrasena

# IDs de usuarios que tienen rol explícito ADMIN en el caso de estudio Salón Spa Rodríguez
IDS_ADMINISTRADORES_INICIALES: frozenset[int] = frozenset({1, 6})

USERNAMES_CANONICOS: dict[int, str] = {
    1: "rosa.admin",
    2: "lucia.spa",
    3: "carmen.spa",
    4: "marco.spa",
    5: "andrea.spa",
    6: "jorge.admin",
}


def configurar_esquema_auth(
    nombre_bd_datos: str | None = None,
    regenerar_existentes: bool = False,
    ruta_salida_claves: Path | None = None,
) -> list[dict[str, str | int]]:
    """
    Crea el esquema `spa_rodriguez_app` con las tablas `credencial` y `bitacora`,
    sincroniza los usuarios de `spa_rodriguez.usuario` y genera contraseñas temporales
    aleatorias con `debe_cambiar = 1`.
    """
    params = obtener_parametros_conexion(nombre_bd=nombre_bd_datos)
    bd_datos = str(params["database"])
    bd_auth = str(params["auth_database"])

    conn = mysql.connector.connect(
        host=str(params["host"]),
        port=int(params["port"]),
        user=str(params["user"]),
        password=str(params["password"]),
        charset="utf8mb4",
        use_unicode=True,
        autocommit=False,
    )
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{bd_auth}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{bd_auth}`.`credencial` (
                id_usuario        INT PRIMARY KEY,
                username          VARCHAR(50) NOT NULL UNIQUE,
                rol               ENUM('ADMIN', 'TRABAJADOR') NOT NULL DEFAULT 'TRABAJADOR',
                hash_clave        VARCHAR(128) NOT NULL,
                salt              VARCHAR(64) NOT NULL,
                iteraciones       INT NOT NULL,
                activo            TINYINT(1) NOT NULL DEFAULT 1,
                debe_cambiar      TINYINT(1) NOT NULL DEFAULT 1,
                intentos_fallidos INT NOT NULL DEFAULT 0,
                bloqueado_hasta   DATETIME NULL,
                ultimo_acceso     DATETIME NULL
            ) ENGINE=InnoDB
            """
        )
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{bd_auth}`.`bitacora` (
                id_bitacora INT AUTO_INCREMENT PRIMARY KEY,
                fecha_hora  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                id_usuario  INT NULL,
                username    VARCHAR(60) NULL,
                accion      VARCHAR(80) NOT NULL,
                detalle     VARCHAR(500) NOT NULL
            ) ENGINE=InnoDB
            """
        )
        conn.commit()

        # Consultar los usuarios de la tabla usuario del modelo de 18 tablas
        cur.execute(f"SELECT id_usuario, nombre FROM `{bd_datos}`.`usuario` ORDER BY id_usuario")
        usuarios = cur.fetchall()

        generadas: list[dict[str, str | int]] = []
        for u in usuarios:
            uid = int(u["id_usuario"])
            nom = str(u["nombre"])
            rol = ROL_ADMIN if uid in IDS_ADMINISTRADORES_INICIALES else ROL_TRABAJADOR
            uname = USERNAMES_CANONICOS.get(uid) or sugerir_username(nom, uid)

            cur.execute(
                f"SELECT id_usuario FROM `{bd_auth}`.`credencial` WHERE id_usuario = %s",
                (uid,),
            )
            existe = cur.fetchone()
            if existe and not regenerar_existentes:
                continue

            clave_temp = generar_clave_temporal()
            hash_hex, salt_hex, iters = generar_hash_contrasena(clave_temp)

            if existe:
                cur.execute(
                    f"""
                    UPDATE `{bd_auth}`.`credencial`
                       SET username = %s,
                           rol = %s,
                           hash_clave = %s,
                           salt = %s,
                           iteraciones = %s,
                           activo = 1,
                           debe_cambiar = 1,
                           intentos_fallidos = 0,
                           bloqueado_hasta = NULL
                     WHERE id_usuario = %s
                    """,
                    (uname, rol, hash_hex, salt_hex, iters, uid),
                )
            else:
                cur.execute(
                    f"""
                    INSERT INTO `{bd_auth}`.`credencial`
                        (id_usuario, username, rol, hash_clave, salt, iteraciones, activo, debe_cambiar, intentos_fallidos)
                    VALUES (%s, %s, %s, %s, %s, %s, 1, 1, 0)
                    """,
                    (uid, uname, rol, hash_hex, salt_hex, iters),
                )

            cur.execute(
                f"""
                INSERT INTO `{bd_auth}`.`bitacora` (id_usuario, username, accion, detalle, fecha_hora)
                VALUES (%s, %s, 'SETUP_CREDENCIAL', %s, NOW())
                """,
                (uid, uname, f"Credencial inicial generada con rol explícito {rol} y clave temporal (debe_cambiar=1)."),
            )
            generadas.append(
                {
                    "id_usuario": uid,
                    "username": uname,
                    "nombre": nom,
                    "rol": rol,
                    "clave_temporal": clave_temp,
                }
            )

        conn.commit()

        if generadas and bd_datos != "spa_copia":
            archivo_salida = ruta_salida_claves or (BASE_DIR / "credenciales_temporales_un_solo_uso.txt")
            lineas = [
                "================================================================================",
                " SALÓN SPA RODRÍGUEZ — CREDENCIALES TEMPORALES DE PRIMER ACCESO (UN SOLO USO)",
                " IMPORTANTE: Entregue a cada operador su clave temporal y ELIMINE este archivo.",
                " En el primer inicio de sesión el sistema obligará a cambiar la contraseña.",
                "================================================================================",
                f"{'ID':<4} | {'USERNAME':<16} | {'ROL':<12} | {'CLAVE TEMPORAL':<18} | {'NOMBRE'}",
                "-" * 80,
            ]
            for item in generadas:
                lineas.append(
                    f"{item['id_usuario']:<4} | {str(item['username']):<16} | {str(item['rol']):<12} | "
                    f"{str(item['clave_temporal']):<18} | {item['nombre']}"
                )
            archivo_salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")

        return generadas
    finally:
        cur.close()
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicializa el esquema spa_rodriguez_app y genera claves temporales PBKDF2.")
    parser.add_argument("--db", default=None, help="Base de datos del modelo principal (por defecto DB_NAME de .env)")
    parser.add_argument("--regenerar", action="store_true", help="Regenera contraseñas temporales para todos los usuarios")
    args = parser.parse_args()

    generadas = configurar_esquema_auth(args.db, regenerar_existentes=args.regenerar)
    if generadas:
        print(
            f"[OK] Se generaron {len(generadas)} credenciales seguras (PBKDF2-HMAC-SHA256) con debe_cambiar=1.\n"
            f"     Consulte el archivo 'credenciales_temporales_un_solo_uso.txt' y bórrelo tras entregar las claves."
        )
    else:
        print("[OK] El esquema spa_rodriguez_app ya tenía credenciales configuradas. Use --regenerar si desea emitir nuevas claves temporales.")


if __name__ == "__main__":
    main()

