# -*- coding: utf-8 -*-
"""
Suite de pruebas automáticas verificables (T1 a T14 y Sección 5 del protocolo).
Ejecuta todas las pruebas sobre una copia aislada (`spa_copia`) y revierte las transacciones
para no dejar datos residuales.

Ejecución:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path
import mysql.connector

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import PROCEDIMIENTOS_REQUERIDOS, TABLAS_MODELO_18, obtener_parametros_conexion
from permisos import ROL_ADMIN, ROL_TRABAJADOR, SesionUsuario
from seguridad import (
    ITERACIONES_PBKDF2,
    generar_clave_temporal,
    generar_hash_contrasena,
    validar_politica_contrasena,
    verificar_contrasena,
)
from servicios import GestorBaseDatos
from setup_auth import configurar_esquema_auth
from setup_procedimientos import instalar_procedimientos

DB_COPIA = "spa_copia"


def preparar_base_copia() -> None:
    """
    Crea `spa_copia` clonando la estructura de 18 tablas, datos limpios y los 2 triggers
    oficiales desde `spa_rodriguez` y `etl_spa/sql/spa_rodriguez.sql` (Sección 5.1).
    Luego instala los procedimientos almacenados y las credenciales en `spa_rodriguez_app`.
    """
    params = obtener_parametros_conexion()
    bd_origen = str(params["database"])
    conn = mysql.connector.connect(
        host=str(params["host"]),
        port=int(params["port"]),
        user=str(params["user"]),
        password=str(params["password"]),
        charset="utf8mb4",
        use_unicode=True,
        autocommit=False,
    )
    cur = conn.cursor()
    try:
        cur.execute(f"DROP DATABASE IF EXISTS `{DB_COPIA}`")
        cur.execute(f"CREATE DATABASE `{DB_COPIA}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.execute(f"USE `{DB_COPIA}`")

        # Crear las 18 tablas y los 2 triggers desde etl_spa/sql/spa_rodriguez.sql
        ruta_ddl = ROOT_DIR / "etl_spa" / "sql" / "spa_rodriguez.sql"
        texto_ddl = ruta_ddl.read_text(encoding="utf-8")
        # Ejecutar creación de tablas (antes de DELIMITER $$)
        parte_tablas = texto_ddl.split("DELIMITER $$")[0]
        for linea_stmt in parte_tablas.split(";"):
            stmt = "\n".join(
                ln for ln in linea_stmt.splitlines() if not ln.strip().startswith("--")
            ).strip()
            if not stmt or stmt.upper().startswith("CREATE DATABASE") or stmt.upper().startswith("USE "):
                continue
            cur.execute(stmt)

        # Copiar los datos limpios desde la base original en orden de llaves foráneas
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        for tabla in TABLAS_MODELO_18:
            cur.execute(f"INSERT INTO `{DB_COPIA}`.`{tabla}` SELECT * FROM `{bd_origen}`.`{tabla}`")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")

        # Crear los 2 triggers oficiales del esquema
        cur.execute(
            """
            CREATE TRIGGER trg_detalle_venta_descuenta_stock
            AFTER INSERT ON detalle_venta
            FOR EACH ROW
            BEGIN
              DECLARE stock_actual INT;
              SELECT stock INTO stock_actual FROM producto
               WHERE codigo_producto = NEW.codigo_producto FOR UPDATE;
              IF stock_actual < NEW.cantidad THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Stock insuficiente para completar la venta';
              ELSE
                UPDATE producto SET stock = stock - NEW.cantidad WHERE codigo_producto = NEW.codigo_producto;
                UPDATE venta SET total = total + NEW.cantidad * NEW.precio WHERE numero_venta = NEW.numero_venta;
              END IF;
            END
            """
        )
        cur.execute(
            """
            CREATE TRIGGER trg_detalle_pedido_aumenta_stock
            AFTER INSERT ON detalle_pedido
            FOR EACH ROW
            BEGIN
              UPDATE producto SET stock = stock + NEW.cantidad WHERE codigo_producto = NEW.codigo_producto;
            END
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    # Instalar procedimientos en spa_copia y en la base principal, e inicializar spa_rodriguez_app
    instalar_procedimientos(DB_COPIA)
    instalar_procedimientos(bd_origen)
    configurar_esquema_auth(DB_COPIA, regenerar_existentes=False)


class TestSistemaSpaRodriguez(unittest.TestCase):
    """Pruebas integrales de aceptación para T1 a T14 sobre `spa_copia`."""

    @classmethod
    def setUpClass(cls) -> None:
        preparar_base_copia()

    def setUp(self) -> None:
        params = obtener_parametros_conexion(nombre_bd=DB_COPIA)
        self. sesion_admin = SesionUsuario(
            id_usuario=1,
            username="rosa.admin",
            nombre="Rosa Rodríguez Salazar",
            rol=ROL_ADMIN,
            debe_cambiar=False,
        )
        self.sesion_trab = SesionUsuario(
            id_usuario=2,
            username="lucia.spa",
            nombre="Lucía Paredes Huamán",
            rol=ROL_TRABAJADOR,
            debe_cambiar=False,
        )
        # autocommit_transaccion=False permite revertir todo en tearDown() sin dejar basura
        self.db = GestorBaseDatos(params=params, sesion=self.sesion_admin, autocommit_transaccion=False)
        self.db.conectar(DB_COPIA)

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.cerrar()

    # ------------------------------------------------------------------
    # T1: ELIMINAR DUPLICACIÓN DE STOCK Y TOTAL (O1)
    # ------------------------------------------------------------------
    def test_t1_venta_y_pedido_no_duplican_stock_ni_total(self) -> None:
        # Producto 3: stock inicial esperado = 54, precio = 42.50
        fila_ini = self.db.consultar("SELECT stock, precio_unitario FROM producto WHERE codigo_producto = 3")[0]
        self.assertEqual(int(fila_ini["stock"]), 54)
        self.assertAlmostEqual(float(fila_ini["precio_unitario"]), 42.50)

        num_venta, nom_prod, total = self.db.registrar_venta_atomica(3, 2)
        self.assertGreater(num_venta, 0)
        self.assertAlmostEqual(total, 85.00, places=2)

        fila_post_venta = self.db.consultar("SELECT stock FROM producto WHERE codigo_producto = 3")[0]
        self.assertEqual(int(fila_post_venta["stock"]), 52, "El stock debía bajar de 54 a 52 (no a 50).")

        fila_venta = self.db.consultar("SELECT total FROM venta WHERE numero_venta = %s", (num_venta,))[0]
        self.assertAlmostEqual(float(fila_venta["total"]), 85.00, places=2, msg="El total debía ser 85.00 (no 170.00).")

        # Pedido de compra de 10 unidades -> stock debe subir exactamente +10 (de 52 a 62)
        id_ped = self.db.registrar_pedido_compra_atomico(1, 1, 3, 10, 20.00)
        self.assertGreater(id_ped, 0)
        fila_post_ped = self.db.consultar("SELECT stock FROM producto WHERE codigo_producto = 3")[0]
        self.assertEqual(int(fila_post_ped["stock"]), 62, "El stock debía subir +10 (de 52 a 62, no +20).")

        # Venta de 9999 unidades -> rechazada, stock intacto
        n_ventas_antes = self.db.consultar("SELECT COUNT(*) AS n FROM venta")[0]["n"]
        with self.assertRaises(ValueError):
            self.db.registrar_venta_atomica(3, 9999)
        fila_tras_fallo = self.db.consultar("SELECT stock FROM producto WHERE codigo_producto = 3")[0]
        self.assertEqual(int(fila_tras_fallo["stock"]), 62)
        n_ventas_despues = self.db.consultar("SELECT COUNT(*) AS n FROM venta")[0]["n"]
        self.assertEqual(n_ventas_antes, n_ventas_despues)

        # Cantidad 0 -> rechazada
        with self.assertRaises(ValueError):
            self.db.registrar_venta_atomica(3, 0)

        # Descuento de 1 botella en cabina -> baja de 62 a 61
        self.db.descontar_botella_cabina_validada(3)
        fila_cabina = self.db.consultar("SELECT stock FROM producto WHERE codigo_producto = 3")[0]
        self.assertEqual(int(fila_cabina["stock"]), 61)

    # ------------------------------------------------------------------
    # T2: PROCEDIMIENTOS SIN COMMIT IMPLÍCITO (O6)
    # ------------------------------------------------------------------
    def test_t2_ausencia_de_commit_implicito_en_procedimientos(self) -> None:
        # Insertar un cliente de prueba dentro de la transacción abierta
        self.db.ejecutar(
            "INSERT INTO cliente (nombres, apellidos, calle, ciudad, id_usuario) VALUES ('ClienteTemporal', 'RollbackTest', 'Calle 1', 'Lima', 1)",
            commit=False,
        )
        # Ejecutar un procedimiento almacenado
        self.db.registrar_venta_atomica(1, 1)
        # Revertir la transacción desde Python
        self.db.rollback()

        # Verificar que el cliente de prueba NO quedó guardado
        filas = self.db.consultar("SELECT * FROM cliente WHERE nombres = 'ClienteTemporal' AND apellidos = 'RollbackTest'")
        self.assertEqual(len(filas), 0, "El procedimiento hizo COMMIT implícito e impidió el ROLLBACK de la aplicación.")

    # ------------------------------------------------------------------
    # T3: AUTENTICACIÓN SEGURA PBKDF2, BLOQUEO Y POLÍTICA (O2, O3, O4)
    # ------------------------------------------------------------------
    def test_t3_seguridad_pbkdf2_bloqueo_y_politica(self) -> None:
        # 1. Ninguna contraseña en texto plano en credencial ni columnas extra en usuario
        cols_usr = [
            r["COLUMN_NAME"].lower()
            for r in self.db.consultar(
                "SELECT COLUMN_NAME FROM information_schema.columns WHERE table_schema = %s AND table_name = 'usuario'",
                (DB_COPIA,),
            )
        ]
        self.assertEqual(cols_usr, ["id_usuario", "nombre", "telefono"], "La tabla usuario no debe tener columnas extra.")

        creds = self.db.consultar(f"SELECT username, hash_clave, salt, iteraciones FROM `{self.db.nombre_bd_auth}`.`credencial`")
        self.assertGreaterEqual(len(creds), 6)
        for c in creds:
            self.assertEqual(len(str(c["hash_clave"])), 64)
            self.assertEqual(len(str(c["salt"])), 32)
            self.assertGreaterEqual(int(c["iteraciones"]), 200_000)
            self.assertNotIn("spa123", str(c["hash_clave"]).lower())
            self.assertNotIn("admin123", str(c["hash_clave"]).lower())

        # 2. Política de contraseñas
        with self.assertRaises(ValueError):
            validar_politica_contrasena("corta1", "rosa.admin")
        with self.assertRaises(ValueError):
            validar_politica_contrasena("sololetras", "rosa.admin")
        with self.assertRaises(ValueError):
            validar_politica_contrasena("123456789", "rosa.admin")
        with self.assertRaises(ValueError):
            validar_politica_contrasena("rosa.admin123", "rosa.admin")
        with self.assertRaises(ValueError):
            validar_politica_contrasena("spa123", "rosa.admin")
        validar_politica_contrasena("ClaveSegura2026", "rosa.admin")

        # 3. Probar login por ID, nombre completo, bloqueo tras 5 intentos y primer ingreso
        params = obtener_parametros_conexion(nombre_bd=DB_COPIA)
        db_auth_test = GestorBaseDatos(params=params, sesion=self.sesion_admin, autocommit_transaccion=True)
        db_auth_test.conectar(DB_COPIA)
        try:
            clave_temp = db_auth_test.restablecer_contrasena_usuario(2)  # lucia.spa

            # Login con ID '2' o con nombre completo debe fallar
            with self.assertRaises(ValueError):
                db_auth_test.iniciar_sesion("2", clave_temp)
            with self.assertRaises(ValueError):
                db_auth_test.iniciar_sesion("Lucía Paredes Huamán", clave_temp)

            # Primer ingreso exitoso con clave temporal -> debe_cambiar = True -> bloquea operaciones hasta cambiarla
            sesion_lucia = db_auth_test.iniciar_sesion("lucia.spa", clave_temp)
            self.assertTrue(sesion_lucia.debe_cambiar)
            with self.assertRaises(PermissionError):
                db_auth_test.registrar_venta_atomica(1, 1)

            # Cambiar contraseña cumpliendo política
            nueva_clave = "LuciaSegura2026"
            db_auth_test.cambiar_contrasena_propia(clave_temp, nueva_clave)
            self.assertFalse(db_auth_test.sesion_actual.debe_cambiar)

            # 5 intentos fallidos consecutivos bloquean la cuenta
            for _ in range(5):
                with self.assertRaises(ValueError):
                    db_auth_test.iniciar_sesion("lucia.spa", "ClaveIncorrecta999")

            # Con la contraseña correcta pero cuenta bloqueada, se rechaza
            with self.assertRaises(ValueError) as ctx:
                db_auth_test.iniciar_sesion("lucia.spa", nueva_clave)
            self.assertIn("bloqueada", str(ctx.exception).lower())

            # Restaurar estado limpio de lucia.spa
            db_auth_test.sesion_actual = self.sesion_admin
            db_auth_test.restablecer_contrasena_usuario(2)
        finally:
            db_auth_test.cerrar()

    # ------------------------------------------------------------------
    # T4: ROL EXPLÍCITO (O5)
    # ------------------------------------------------------------------
    def test_t4_rol_explicito_no_depende_de_tabla_empleado(self) -> None:
        # Borrar la fila de Marco (id_usuario = 4) en empleado dentro de la transacción
        self.db.ejecutar("DELETE FROM empleado WHERE id_usuario = 4", commit=False)
        usuarios = self.db.obtener_usuarios_detallados()
        marco = next(u for u in usuarios if int(u["id_usuario"]) == 4)
        self.assertEqual(marco["rol_codigo"], ROL_TRABAJADOR, "Borrar empleado no debe convertir a Marco en ADMIN.")

        # Con sesión de Marco, intentar emitir pedido de compra falla por permisos y en SQL
        self.db.sesion_actual = SesionUsuario(id_usuario=4, username="marco.spa", nombre="Marco Quispe Ramos", rol=ROL_TRABAJADOR)
        with self.assertRaises(PermissionError):
            self.db.registrar_pedido_compra_atomico(4, 1, 1, 5, 20.00)

    # ------------------------------------------------------------------
    # T5: NO MODIFICAR LA BASE AL CONECTARSE Y CÓDIGO LIMPIO (O7)
    # ------------------------------------------------------------------
    def test_t5_sin_ddl_al_conectar_ni_except_pass_ni_rutas_personales(self) -> None:
        archivos_codigo = [
            ROOT_DIR / "config.py",
            ROOT_DIR / "db.py",
            ROOT_DIR / "seguridad.py",
            ROOT_DIR / "permisos.py",
            ROOT_DIR / "auth.py",
            ROOT_DIR / "servicios.py",
            ROOT_DIR / "sistema_usuarios_spa.py",
            ROOT_DIR / "ui" / "portal_app.py",
        ]
        patrones_prohibidos = ("ALTER TABLE", "DROP TRIGGER", "CREATE TRIGGER", "DROP PROCEDURE", "dylan_dnxqp1x", "123456789")
        for ruta in archivos_codigo:
            texto = ruta.read_text(encoding="utf-8")
            for pat in patrones_prohibidos:
                self.assertNotIn(pat, texto, f"Se encontró '{pat}' en el archivo de ejecución {ruta.name}.")
            self.assertIsNone(
                re.search(r"(?<!SHOW\s)CREATE\s+PROCEDURE\s+", texto, flags=re.IGNORECASE),
                f"Se encontró 'CREATE PROCEDURE' (DDL) en el archivo de ejecución {ruta.name}.",
            )

            # Verificar con AST que no exista ningún `except ...: pass`
            arbol = ast.parse(texto, filename=str(ruta))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.ExceptHandler):
                    if len(nodo.body) == 1 and isinstance(nodo.body[0], ast.Pass):
                        self.fail(f"Se encontró 'except ...: pass' en {ruta.name} línea {nodo.lineno}.")

        # Verificar que si se borra un procedimiento, conectar NO lo reinstala sino que lo reporta como faltante
        conn = self.db.asegurar_conexion()
        cur = conn.cursor()
        try:
            cur.execute("DROP PROCEDURE IF EXISTS sp_descontar_botella_cabina")
            conn.commit()
            db_check = GestorBaseDatos(params=obtener_parametros_conexion(nombre_bd=DB_COPIA))
            db_check.conectar(DB_COPIA)
            self.assertIn("sp_descontar_botella_cabina", db_check.procedimientos_faltantes)
            db_check.cerrar()
        finally:
            cur.close()
            instalar_procedimientos(DB_COPIA)

    # ------------------------------------------------------------------
    # T6: AUTORIZACIÓN EN LA CAPA DE DATOS (O9)
    # ------------------------------------------------------------------
    def test_t6_autorizacion_capa_datos_y_proteccion_admin(self) -> None:
        # Con sesión de trabajador, los métodos exclusivos de ADMIN lanzan PermissionError
        self.db.sesion_actual = self.sesion_trab
        with self.assertRaises(PermissionError):
            self.db.eliminar_cliente(1)
        with self.assertRaises(PermissionError):
            self.db.eliminar_cita(1)
        with self.assertRaises(PermissionError):
            self.db.registrar_pedido_compra_atomico(2, 1, 1, 5, 15.0)
        with self.assertRaises(PermissionError):
            self.db.agregar_usuario("Nuevo", "999888777")

        # Un administrador no puede eliminarse, desactivarse ni cambiarse el rol a sí mismo
        self.db.sesion_actual = self.sesion_admin
        with self.assertRaises(PermissionError):
            self.db.eliminar_usuario(1)
        with self.assertRaises(PermissionError):
            self.db.actualizar_usuario(1, "Rosa Rodríguez Salazar", "987654321", ROL_TRABAJADOR, activo=True)
        with self.assertRaises(PermissionError):
            self.db.actualizar_usuario(1, "Rosa Rodríguez Salazar", "987654321", ROL_ADMIN, activo=False)

    # ------------------------------------------------------------------
    # T7: CICLO DE VIDA DE LA CITA Y PROPIEDAD POR TRABAJADOR (O8, O9)
    # ------------------------------------------------------------------
    def test_t7_ciclo_vida_cita_y_propiedad(self) -> None:
        # Crear una cita nueva para la trabajadora Lucía (id_usuario = 2) -> empieza en 'Pendiente'
        self.db.sesion_actual = self.sesion_trab
        num_cita = self.db.registrar_cita_validada("2026-12-10", "09:00", 1, "Prueba ciclo", nombre_cliente="Ana Torres")

        # Pendiente -> Atendida directamente debe ser rechazada
        with self.assertRaises(ValueError):
            self.db.cambiar_estado_cita_validado(num_cita, "Atendida")

        # Otro trabajador (id_usuario = 3, Carmen) intentando cambiar la cita de Lucía -> rechazado
        self.db.sesion_actual = SesionUsuario(id_usuario=3, username="carmen.spa", nombre="Carmen Soto", rol=ROL_TRABAJADOR)
        with self.assertRaises(ValueError):
            self.db.cambiar_estado_cita_validado(num_cita, "Confirmada")

        # Lucía confirma su propia cita (Pendiente -> Confirmada) -> aceptada
        self.db.sesion_actual = self.sesion_trab
        self.db.cambiar_estado_cita_validado(num_cita, "Confirmada")

        # Confirmada -> Atendida -> aceptada
        self.db.cambiar_estado_cita_validado(num_cita, "Atendida")

        # Atendida -> Pendiente o Cancelada -> rechazada
        with self.assertRaises(ValueError):
            self.db.cambiar_estado_cita_validado(num_cita, "Pendiente")
        with self.assertRaises(ValueError):
            self.db.cambiar_estado_cita_validado(num_cita, "Cancelada")

        # Cita cancelada no puede volver a ningún estado
        num_cita2 = self.db.registrar_cita_validada("2026-12-10", "14:00", 1, "Prueba cancelada", nombre_cliente="Ana Torres")
        self.db.cambiar_estado_cita_validado(num_cita2, "Cancelada")
        with self.assertRaises(ValueError):
            self.db.cambiar_estado_cita_validado(num_cita2, "Confirmada")

    # ------------------------------------------------------------------
    # T8: CITAS SIN SUPERPOSICIÓN Y SIN PASAR DE LAS 24:00 (O10)
    # ------------------------------------------------------------------
    def test_t8_control_horario_y_no_solapamiento_citas(self) -> None:
        # Servicio 1 dura 60 minutos
        c1 = self.db.registrar_cita_validada("2026-12-15", "10:00", 1, "Masaje", id_usuario=2, nombre_cliente="María López")
        self.assertGreater(c1, 0)

        # Verificar que el cliente se guardó al inicio de observaciones
        fila_c1 = self.db.consultar("SELECT observaciones, hora_fin FROM cita WHERE numero_registro = %s", (c1,))[0]
        self.assertTrue(str(fila_c1["observaciones"]).startswith("Cliente: María López."))

        # Cita a las 10:30 del mismo usuario y día -> rechazada por solapamiento
        with self.assertRaises(ValueError):
            self.db.registrar_cita_validada("2026-12-15", "10:30", 1, "Solapada", id_usuario=2)

        # Cita contigua a las 11:00 del mismo usuario y día -> aceptada
        c2 = self.db.registrar_cita_validada("2026-12-15", "11:00", 1, "Contigua", id_usuario=2)
        self.assertGreater(c2, 0)

        # Cita a las 23:30 con servicio de 60 minutos (terminaría 24:30) -> rechazada
        with self.assertRaises(ValueError):
            self.db.registrar_cita_validada("2026-12-15", "23:30", 1, "Pasa medianoche", id_usuario=2)

    # ------------------------------------------------------------------
    # T9: CLIENTES Y PREFERENCIAS EXCLUSIVAS DEL CATÁLOGO (O11, O12)
    # ------------------------------------------------------------------
    def test_t9_preferencias_solo_del_catalogo(self) -> None:
        n_prefs_antes = self.db.consultar("SELECT COUNT(*) AS n FROM preferencia")[0]["n"]

        # Preferencia inexistente debe fallar y no ensuciar el catálogo
        with self.assertRaises(ValueError):
            self.db.registrar_cliente_validado("Laura", "Méndez", "Av. Arequipa 100", "Miraflores", "Preferencia con errror")

        n_prefs_despues = self.db.consultar("SELECT COUNT(*) AS n FROM preferencia")[0]["n"]
        self.assertEqual(n_prefs_antes, n_prefs_despues, "El catálogo de preferencias no debe cambiar de tamaño.")

        # Preferencia existente en el catálogo debe aceptarse
        pref_valida = self.db.listar_preferencias_catalogo()[0]
        cod_cli = self.db.registrar_cliente_validado("Laura", "Méndez", "Av. Arequipa 100", "Miraflores", pref_valida)
        self.assertGreater(cod_cli, 0)

    # ------------------------------------------------------------------
    # T10: CARRITO DE VENTA CON MÚLTIPLES PRODUCTOS ATÓMICO (O13)
    # ------------------------------------------------------------------
    def test_t10_venta_carrito_multiproducto_todo_o_nada(self) -> None:
        s1_antes = int(self.db.consultar("SELECT stock FROM producto WHERE codigo_producto = 1")[0]["stock"])
        s2_antes = int(self.db.consultar("SELECT stock FROM producto WHERE codigo_producto = 2")[0]["stock"])

        # Caso exitoso con 2 productos
        num_v, total = self.db.registrar_venta_carrito_atomica(
            [
                {"codigo_producto": 1, "cantidad": 2},
                {"codigo_producto": 2, "cantidad": 1},
            ]
        )
        self.assertGreater(num_v, 0)
        self.assertGreater(total, 0)

        s1_post = int(self.db.consultar("SELECT stock FROM producto WHERE codigo_producto = 1")[0]["stock"])
        s2_post = int(self.db.consultar("SELECT stock FROM producto WHERE codigo_producto = 2")[0]["stock"])
        self.assertEqual(s1_post, s1_antes - 2)
        self.assertEqual(s2_post, s2_antes - 1)

        # Caso fallido: el segundo producto pide 99999 unidades -> no se debe descontar el primero
        with self.assertRaises(ValueError):
            self.db.registrar_venta_carrito_atomica(
                [
                    {"codigo_producto": 1, "cantidad": 3},
                    {"codigo_producto": 2, "cantidad": 99999},
                ]
            )
        self.db.rollback()
        s1_rollback = int(self.db.consultar("SELECT stock FROM producto WHERE codigo_producto = 1")[0]["stock"])
        self.assertEqual(s1_rollback, s1_antes, "Al fallar el segundo producto del carrito, no debe descontarse ninguno.")

    # ------------------------------------------------------------------
    # T11 y PROTOCOLO 5.4: BITÁCORA PERSISTENTE Y SUPERVIVENCIA TRAS RE-EJECUTAR ETL
    # ------------------------------------------------------------------
    def test_t11_bitacora_persistente_y_supervivencia_etl(self) -> None:
        # Registrar evento persistente en bitácora
        self.db.auth.registrar_bitacora("TEST_PERSISTENCIA", "Evento de prueba antes de ejecutar ETL", id_usuario=1, username="rosa.admin", commit=True)
        creds_antes = self.db.consultar(f"SELECT id_usuario, username, rol, hash_clave FROM `{self.db.nombre_bd_auth}`.`credencial` ORDER BY id_usuario")
        self.assertGreaterEqual(len(creds_antes), 6)

        # Ejecutar etl_spa.py (trunca y recarga las 18 tablas de spa_rodriguez)
        etl_script = ROOT_DIR / "etl_spa" / "etl_spa.py"
        res = subprocess.run([sys.executable, str(etl_script)], cwd=str(etl_script.parent), capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res.returncode, 0, f"El ETL falló: {res.stderr}")

        # Reinstalar procedimientos en spa_rodriguez tras el ETL (por si se recreó) y verificar que credencial y bitacora siguen intactas
        instalar_procedimientos("spa_rodriguez")
        creds_despues = self.db.consultar(f"SELECT id_usuario, username, rol, hash_clave FROM `{self.db.nombre_bd_auth}`.`credencial` ORDER BY id_usuario")
        self.assertEqual(creds_antes, creds_despues, "Las credenciales en spa_rodriguez_app deben sobrevivir intactas tras ejecutar etl_spa.py.")

        eventos = self.db.auth.consultar_bitacora(filtro="TEST_PERSISTENCIA")
        self.assertGreaterEqual(len(eventos), 1, "La bitácora en spa_rodriguez_app debe sobrevivir tras ejecutar etl_spa.py.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
