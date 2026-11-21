# -*- coding: utf-8 -*-
"""
Script de instalación única del archivo SQL unificado (`sql/procedimientos.sql`)
sobre la base de datos `spa_rodriguez` (crea las tablas de autenticación/bitácora
y los 7 Procedimientos Almacenados SQL).

Uso:
    python setup_procedimientos.py [--db spa_rodriguez]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import mysql.connector

from config import BASE_DIR, PROCEDIMIENTOS_REQUERIDOS, obtener_parametros_conexion


def extraer_bloques_sql(ruta_sql: Path) -> list[str]:
    """Extrae todas las sentencias SQL respetando cambios de DELIMITER (; y $$)."""
    delim = ";"
    buf: list[str] = []
    sentencias: list[str] = []
    for linea in ruta_sql.read_text(encoding="utf-8").splitlines():
        s = linea.strip()
        if not s or s.startswith("--"):
            continue
        if s.upper().startswith("DELIMITER "):
            delim = s.split()[1]
            continue
        buf.append(linea)
        if s.endswith(delim):
            bloque = "\n".join(buf).rstrip()
            bloque = bloque[: -len(delim)].strip()
            buf = []
            if bloque and not bloque.upper().startswith("USE ") and not bloque.upper().startswith("SET NAMES"):
                sentencias.append(bloque)
    return sentencias


def instalar_procedimientos(nombre_bd: str | None = None) -> list[str]:
    params = obtener_parametros_conexion(nombre_bd=nombre_bd)
    bd_destino = str(params["database"])
    ruta_sql = BASE_DIR / "sql" / "procedimientos.sql"
    if not ruta_sql.exists():
        raise FileNotFoundError(f"No se encontró el archivo SQL unificado en: {ruta_sql}")

    sentencias = extraer_bloques_sql(ruta_sql)
    conn = mysql.connector.connect(
        host=str(params["host"]),
        port=int(params["port"]),
        user=str(params["user"]),
        password=str(params["password"]),
        database=bd_destino,
        charset="utf8mb4",
        use_unicode=True,
        autocommit=False,
    )
    cur = conn.cursor()
    try:
        cur.execute("DROP TRIGGER IF EXISTS trg_validar_venta_stock_before_insert")
        for stmt in sentencias:
            cur.execute(stmt)
        conn.commit()

        cur.execute(
            """
            SELECT routine_name
              FROM information_schema.routines
             WHERE routine_schema = %s AND routine_type = 'PROCEDURE'
             ORDER BY routine_name
            """,
            (bd_destino,),
        )
        instalados = [str(r[0]) for r in cur.fetchall()]
        faltantes = [sp for sp in PROCEDIMIENTOS_REQUERIDOS if sp not in instalados]
        if faltantes:
            raise RuntimeError(f"Faltaron instalar procedimientos en {bd_destino}: {faltantes}")
        return instalados
    finally:
        cur.close()
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Instala el script SQL unificado (sql/procedimientos.sql) en spa_rodriguez.")
    parser.add_argument("--db", default=None, help="Nombre de la base de datos destino (por defecto usa DB_NAME de .env)")
    args = parser.parse_args()

    instalados = instalar_procedimientos(args.db)
    bd_mostrar = args.db or obtener_parametros_conexion()["database"]
    print(f"[OK] Tablas de seguridad y {len(instalados)} procedimientos almacenados instalados en '{bd_mostrar}':")
    for sp in instalados:
        print(f"  - {sp}")


if __name__ == "__main__":
    main()
