# -*- coding: utf-8 -*-
"""
Interfaz gráfica Tkinter del Salón Spa Rodríguez (T12 y T13).
Separa la presentación de la capa de servicios (`servicios.py`) y autenticación (`auth.py`).
Cumple con:
- Cero contraseñas visibles en tablas o formularios (T3: O4).
- Cambio obligatorio de contraseña temporal en el primer inicio de sesión (T3).
- Combos cerrados (`readonly`) para catálogos de preferencias, especialidades y estados (T9, T13).
- Sin campo de teléfono en el formulario de clientes (modelo físico de 18 tablas, T9: O11).
- Un trabajador solo ve y gestiona sus propias citas, sin casilla para ver citas ajenas (T6: O9).
- Carrito de venta multiproducto atómico (T10: O13).
- Etiquetas de indicadores exactas («Citas Reg. / Atend.», «Unidades en Stock», «Personal Activo») (T13).
- Bitácora persistente consultada desde `spa_rodriguez_app.bitacora` (T11).
"""
from __future__ import annotations

import datetime as dt
import re
import tkinter as tk
from tkinter import messagebox, ttk

from config import RN
from permisos import ROL_ADMIN, ROL_TRABAJADOR, SesionUsuario
from servicios import GestorBaseDatos

COLOR_SIDEBAR_ADMIN = "#1E293B"
COLOR_SIDEBAR_TRAB = "#064E3B"
COLOR_BTN_ADMIN = "#334155"
COLOR_BTN_TRAB = "#047857"
COLOR_ACT_ADMIN = "#2563EB"
COLOR_ACT_TRAB = "#10B981"
COLOR_BG = "#F1F5F9"
COLOR_CARD = "#FFFFFF"
COLOR_PRIMARY = "#1D4ED8"
COLOR_SUCCESS = "#059669"
COLOR_DANGER = "#DC2626"
COLOR_WARNING = "#D97706"
COLOR_TEXT = "#0F172A"
COLOR_MUTED = "#64748B"


class PortalUsuariosSpaApp(tk.Tk):
    """Aplicación de escritorio por roles (ADMIN / TRABAJADOR) conectada a MySQL 8.0."""

    def __init__(self, db: GestorBaseDatos):
        super().__init__()
        self.db = db
        self.title("Salón Spa Rodríguez — Portal Operativo (Seguridad PBKDF2 & Procedimientos SQL)")
        self.geometry("1280x760")
        self.minsize(1080, 660)
        self.configure(bg=COLOR_BG)

        self._configurar_estilos()
        self.root_container = tk.Frame(self, bg=COLOR_BG)
        self.root_container.pack(fill=tk.BOTH, expand=True)

        self.mostrar_pantalla_login()

    @property
    def usuario_actual(self) -> SesionUsuario | None:
        return self.db.sesion_actual

    def _configurar_estilos(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=27, background="white", fieldbackground="white")
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background="#1E3A8A",
            foreground="white",
            padding=(6, 5),
        )
        style.map("Treeview", background=[("selected", "#DBEAFE")], foreground=[("selected", "#1E3A8A")])
        style.configure("TCombobox", padding=4, font=("Segoe UI", 9))

    def _limpiar_root(self) -> None:
        for w in self.root_container.winfo_children():
            w.destroy()

    # ==================================================================
    # 1. PANTALLA DE INICIO DE SESIÓN Y VERIFICACIÓN DE INSTALACIÓN (T3, T5)
    # ==================================================================
    def mostrar_pantalla_login(self) -> None:
        self._limpiar_root()

        top = tk.Frame(self.root_container, bg="#0F172A", height=58)
        top.pack(fill=tk.X)
        top.pack_propagate(False)

        tk.Label(
            top,
            text="✨ SALÓN SPA RODRÍGUEZ — PORTAL DE ACCESO PARA TRABAJADORES Y ADMINISTRADORES",
            font=("Segoe UI", 12, "bold"),
            bg="#0F172A",
            fg="white",
        ).pack(side=tk.LEFT, padx=22)

        tk.Label(
            top,
            text=f"Base de Datos Activa (.env): {self.db.nombre_bd}",
            font=("Segoe UI", 9, "bold"),
            bg="#1E293B",
            fg="#38BDF8",
            padx=12,
            pady=4,
        ).pack(side=tk.RIGHT, padx=22)

        # Verificar estado de instalación sin ejecutar DDL (T5)
        faltantes_sp = self.db.verificar_procedimientos()
        auth_ok = self.db.auth.verificar_esquema_auth_instalado()
        if faltantes_sp or not auth_ok:
            aviso = tk.Frame(self.root_container, bg="#FEF2F2", highlightbackground="#EF4444", highlightthickness=1)
            aviso.pack(fill=tk.X, padx=24, pady=(12, 0))
            detalles = []
            if not auth_ok:
                detalles.append("Falta inicializar el esquema `spa_rodriguez_app` (ejecute: python setup_auth.py).")
            if faltantes_sp:
                detalles.append(
                    f"Faltan procedimientos almacenados ({', '.join(faltantes_sp)}) (ejecute: python setup_procedimientos.py)."
                )
            tk.Label(
                aviso,
                text="⚠️ Instalación pendiente: " + " | ".join(detalles),
                font=("Segoe UI", 9, "bold"),
                bg="#FEF2F2",
                fg="#991B1B",
                pady=8,
                padx=12,
            ).pack(anchor="w")

        wrapper = tk.Frame(self.root_container, bg=COLOR_BG)
        wrapper.pack(fill=tk.BOTH, expand=True)

        card = tk.Frame(wrapper, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1)
        card.place(relx=0.5, rely=0.5, anchor="center", width=780, height=450)

        brand = tk.Frame(card, bg="#0F172A", width=300)
        brand.pack(side=tk.LEFT, fill=tk.Y)
        brand.pack_propagate(False)

        tk.Label(
            brand,
            text="✨ SALÓN SPA\nRODRÍGUEZ",
            font=("Segoe UI", 18, "bold"),
            bg="#0F172A",
            fg="white",
            justify="left",
        ).pack(anchor="w", padx=28, pady=(42, 12))

        tk.Frame(brand, bg="#3B82F6", height=3, width=65).pack(anchor="w", padx=28, pady=(0, 18))

        tk.Label(
            brand,
            text=(
                "Portal Operativo de Atención,\n"
                "Agenda de Citas e Inventario.\n\n"
                "Autenticación segura mediante\n"
                "PBKDF2-HMAC-SHA256 y control\n"
                "de acceso explícito por rol:\n\n"
                "• Especialistas de Cabina (TRABAJADOR)\n"
                "• Recepción y Gerencia (ADMIN)"
            ),
            font=("Segoe UI", 9),
            bg="#0F172A",
            fg="#CBD5E1",
            justify="left",
        ).pack(anchor="w", padx=28)

        tk.Label(
            brand,
            text=f"● Conectado a {self.db.nombre_bd} (18 tablas)",
            font=("Segoe UI", 8, "bold"),
            bg="#0F172A",
            fg="#34D399",
        ).pack(side=tk.BOTTOM, anchor="w", padx=28, pady=22)

        form = tk.Frame(card, bg=COLOR_CARD, padx=42, pady=36)
        form.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            form,
            text="🔐 Iniciar Sesión",
            font=("Segoe UI", 17, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        ).pack(anchor="w")

        tk.Label(
            form,
            text="Ingrese exclusivamente su nombre de usuario (username) y contraseña.",
            font=("Segoe UI", 9),
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
        ).pack(anchor="w", pady=(4, 22))

        tk.Label(form, text="Usuario (username) (*):", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT).pack(anchor="w")
        self.var_login_user = tk.StringVar()
        ent_user = tk.Entry(
            form,
            textvariable=self.var_login_user,
            font=("Segoe UI", 11),
            bg="#F8FAFC",
            relief=tk.SOLID,
            bd=1,
        )
        ent_user.pack(fill=tk.X, pady=(5, 16), ipady=6)
        ent_user.focus_set()

        tk.Label(form, text="Contraseña (*):", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT).pack(anchor="w")
        pwd_frame = tk.Frame(form, bg=COLOR_CARD)
        pwd_frame.pack(fill=tk.X, pady=(5, 8))

        self.var_login_pwd = tk.StringVar()
        self.ent_login_pwd = tk.Entry(
            pwd_frame,
            textvariable=self.var_login_pwd,
            font=("Segoe UI", 11),
            show="●",
            bg="#F8FAFC",
            relief=tk.SOLID,
            bd=1,
        )
        self.ent_login_pwd.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        self.ent_login_pwd.bind("<Return>", lambda _e: self._intentar_login())

        self.var_mostrar_pwd = tk.BooleanVar(value=False)

        def _toggle_pwd() -> None:
            self.ent_login_pwd.configure(show="" if self.var_mostrar_pwd.get() else "●")

        tk.Checkbutton(
            pwd_frame,
            text="Mostrar",
            variable=self.var_mostrar_pwd,
            command=_toggle_pwd,
            bg=COLOR_CARD,
            font=("Segoe UI", 8),
        ).pack(side=tk.LEFT, padx=(8, 0))

        self.lbl_error_login = tk.Label(
            form,
            text="",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_DANGER,
            wraplength=380,
            justify="left",
        )
        self.lbl_error_login.pack(anchor="w", pady=(4, 10))

        tk.Button(
            form,
            text="INGRESAR AL SISTEMA",
            command=self._intentar_login,
            bg=COLOR_PRIMARY,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            pady=10,
            cursor="hand2",
        ).pack(fill=tk.X, pady=(4, 8))

        tk.Label(
            form,
            text="🔒 Bloqueo automático por 5 minutos tras 5 intentos fallidos.",
            font=("Segoe UI", 8),
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
        ).pack(anchor="w")

    def _intentar_login(self) -> None:
        usr = self.var_login_user.get().strip()
        pwd = self.var_login_pwd.get()
        self.var_login_pwd.set("")  # Limpiar contraseña en memoria inmediatamente (T3)

        try:
            sesion = self.db.iniciar_sesion(usr, pwd)
        except Exception as err:
            self.lbl_error_login.configure(text=f"❌ {err}")
            return

        if sesion.debe_cambiar:
            self.mostrar_pantalla_cambio_clave_obligatorio(clave_temporal_usada=pwd)
        else:
            self.mostrar_entorno_trabajo()

    # ==================================================================
    # 2. CAMBIO OBLIGATORIO DE CONTRASEÑA EN PRIMER INGRESO (T3)
    # ==================================================================
    def mostrar_pantalla_cambio_clave_obligatorio(self, clave_temporal_usada: str = "") -> None:
        self._limpiar_root()
        sesion = self.usuario_actual
        assert sesion is not None

        wrapper = tk.Frame(self.root_container, bg=COLOR_BG)
        wrapper.pack(fill=tk.BOTH, expand=True)

        card = tk.Frame(wrapper, bg=COLOR_CARD, highlightbackground="#F59E0B", highlightthickness=2, padx=36, pady=30)
        card.place(relx=0.5, rely=0.5, anchor="center", width=540, height=430)

        tk.Label(
            card,
            text="🔑 Cambio Obligatorio de Contraseña",
            font=("Segoe UI", 15, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        ).pack(anchor="w")

        tk.Label(
            card,
            text=(
                f"Bienvenido(a), {sesion.nombre} ({sesion.username}).\n"
                "Por seguridad, debe establecer una contraseña personal antes de acceder al sistema.\n"
                "Política: mínimo 8 caracteres, incluir letras y números, y ser distinta a su usuario."
            ),
            font=("Segoe UI", 9),
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
            justify="left",
            wraplength=460,
        ).pack(anchor="w", pady=(6, 16))

        tk.Label(card, text="Contraseña Actual / Temporal (*):", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD).pack(anchor="w")
        var_act = tk.StringVar(value=clave_temporal_usada)
        tk.Entry(card, textvariable=var_act, show="●", font=("Segoe UI", 10), bg="#F8FAFC").pack(fill=tk.X, pady=(2, 10), ipady=4)

        tk.Label(card, text="Nueva Contraseña Personal (*):", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD).pack(anchor="w")
        var_nva = tk.StringVar()
        tk.Entry(card, textvariable=var_nva, show="●", font=("Segoe UI", 10), bg="#F8FAFC").pack(fill=tk.X, pady=(2, 10), ipady=4)

        tk.Label(card, text="Confirmar Nueva Contraseña (*):", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD).pack(anchor="w")
        var_conf = tk.StringVar()
        tk.Entry(card, textvariable=var_conf, show="●", font=("Segoe UI", 10), bg="#F8FAFC").pack(fill=tk.X, pady=(2, 14), ipady=4)

        def _confirmar() -> None:
            if var_nva.get() != var_conf.get():
                messagebox.showwarning("Validación", "La confirmación no coincide con la nueva contraseña.")
                return
            try:
                self.db.cambiar_contrasena_propia(var_act.get(), var_nva.get())
                var_act.set("")
                var_nva.set("")
                var_conf.set("")
                messagebox.showinfo("Contraseña Actualizada", "Su contraseña personal ha sido guardada. Bienvenido(a) al sistema.")
                self.mostrar_entorno_trabajo()
            except Exception as err:
                messagebox.showerror("Política de Contraseña", str(err))

        btn_row = tk.Frame(card, bg=COLOR_CARD)
        btn_row.pack(fill=tk.X, pady=(6, 0))
        tk.Button(
            btn_row,
            text="GUARDAR Y CONTINUAR",
            command=_confirmar,
            bg=COLOR_SUCCESS,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            padx=18,
            pady=8,
        ).pack(side=tk.LEFT)
        tk.Button(
            btn_row,
            text="Cancelar / Cerrar Sesión",
            command=self._cerrar_sesion_ui,
            bg="#E2E8F0",
            fg=COLOR_TEXT,
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=14,
            pady=8,
        ).pack(side=tk.RIGHT)

    def _cerrar_sesion_ui(self) -> None:
        self.db.cerrar_sesion()
        self.mostrar_pantalla_login()

    # ==================================================================
    # 3. ENTORNO DE TRABAJO POR ROL (ADMIN vs TRABAJADOR)
    # ==================================================================
    def mostrar_entorno_trabajo(self) -> None:
        self._limpiar_root()
        sesion = self.usuario_actual
        assert sesion is not None

        es_admin = sesion.es_admin
        color_sb = COLOR_SIDEBAR_ADMIN if es_admin else COLOR_SIDEBAR_TRAB
        color_btn = COLOR_BTN_ADMIN if es_admin else COLOR_BTN_TRAB
        color_act = COLOR_ACT_ADMIN if es_admin else COLOR_ACT_TRAB

        header = tk.Frame(self.root_container, bg=color_sb, height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        icono_rol = "👑 ADMINISTRADOR" if es_admin else "🌿 TRABAJADOR"
        tk.Label(
            header,
            text=f"✨ Salón Spa Rodríguez  |  {icono_rol}: {sesion.nombre} ({sesion.username})",
            font=("Segoe UI", 11, "bold"),
            bg=color_sb,
            fg="white",
        ).pack(side=tk.LEFT, padx=18)

        tk.Button(
            header,
            text="🚪 Cerrar Sesión",
            command=self._cerrar_sesion_ui,
            bg=COLOR_DANGER,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=4,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=18)

        body = tk.Frame(self.root_container, bg=COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True)

        sidebar = tk.Frame(body, bg=color_sb, width=250)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        self.main_area = tk.Frame(body, bg=COLOR_BG)
        self.main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=16, pady=14)

        if es_admin:
            modulos = [
                ("panel", "📊  Panel General"),
                ("citas", "📅  Agenda de Citas"),
                ("clientes", "👥  Clientes y Preferencias"),
                ("ventas_inv", "🛒  Ventas (Carrito) y Stock"),
                ("compras", "📦  Compras a Proveedores"),
                ("usuarios", "🔐  Usuarios y Credenciales"),
                ("procedimientos", "⚙️  Proc. Almacenados y RN"),
                ("bitacora", "📜  Bitácora Persistente"),
                ("perfil", "👤  Mi Perfil y Contraseña"),
            ]
        else:
            modulos = [
                ("panel", "📊  Mi Panel Operativo"),
                ("citas", "📅  Mis Citas Asignadas"),
                ("clientes", "👥  Registro de Clientes"),
                ("ventas_inv", "🛒  Ventas y Consumo Cabina"),
                ("procedimientos", "⚙️  Proc. Almacenados y RN"),
                ("perfil", "👤  Mi Perfil y Contraseña"),
            ]

        self.botones_menu: dict[str, tk.Button] = {}
        tk.Label(
            sidebar,
            text="MÓDULOS HABILITADOS",
            font=("Segoe UI", 8, "bold"),
            bg=color_sb,
            fg="#94A3B8",
        ).pack(anchor="w", padx=16, pady=(14, 6))

        for clave, texto in modulos:
            btn = tk.Button(
                sidebar,
                text=texto,
                anchor="w",
                font=("Segoe UI", 9, "bold"),
                bg=color_btn,
                fg="white",
                activebackground=color_act,
                activeforeground="white",
                relief=tk.FLAT,
                padx=14,
                pady=9,
                cursor="hand2",
                command=lambda k=clave: self._abrir_modulo(k),
            )
            btn.pack(fill=tk.X, padx=10, pady=3)
            self.botones_menu[clave] = btn

        self._abrir_modulo("panel")

    def _limpiar_main(self) -> None:
        for w in self.main_area.winfo_children():
            w.destroy()

    def _abrir_modulo(self, clave: str) -> None:
        sesion = self.usuario_actual
        assert sesion is not None
        color_btn = COLOR_BTN_ADMIN if sesion.es_admin else COLOR_BTN_TRAB
        color_act = COLOR_ACT_ADMIN if sesion.es_admin else COLOR_ACT_TRAB
        for k, b in self.botones_menu.items():
            b.configure(bg=color_act if k == clave else color_btn)

        self._limpiar_main()
        mapa = {
            "panel": self._modulo_panel,
            "citas": self._modulo_citas,
            "clientes": self._modulo_clientes,
            "ventas_inv": self._modulo_ventas_inventario,
            "compras": self._modulo_compras_admin,
            "usuarios": self._modulo_usuarios_admin,
            "procedimientos": self._modulo_procedimientos_almacenados,
            "bitacora": self._modulo_bitacora,
            "perfil": self._modulo_perfil,
        }
        func = mapa.get(clave, self._modulo_panel)
        func()

    # ==================================================================
    # MÓDULO 1: PANEL GENERAL CON ETIQUETAS EXACTAS (T13)
    # ==================================================================
    def _modulo_panel(self) -> None:
        sesion = self.usuario_actual
        assert sesion is not None

        tk.Label(
            self.main_area,
            text=f"📊 Panel Operativo — {sesion.nombre} ({sesion.rol_etiqueta})",
            font=("Segoe UI", 15, "bold"),
            bg=COLOR_BG,
            fg=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 12))

        kpi_frame = tk.Frame(self.main_area, bg=COLOR_BG)
        kpi_frame.pack(fill=tk.X, pady=(0, 14))

        citas_reg = self.db.consultar("SELECT COUNT(*) AS n FROM cita")[0]["n"]
        citas_atend = self.db.consultar(
            "SELECT COUNT(*) AS n FROM cita c JOIN estado_cita e ON e.id_estado = c.id_estado WHERE e.descripcion = 'Atendida'"
        )[0]["n"]
        unidades_stock = self.db.consultar("SELECT COALESCE(SUM(stock), 0) AS s FROM producto")[0]["s"]
        cuentas_activas = self.db.consultar(
            f"SELECT COUNT(*) AS n FROM `{self.db.nombre_bd_auth}`.`credencial` WHERE activo = 1"
        )[0]["n"]
        especialistas_cabina = self.db.consultar("SELECT COUNT(DISTINCT id_usuario) AS n FROM empleado")[0]["n"]
        ventas_tot = self.db.consultar("SELECT COALESCE(SUM(total), 0) AS t FROM venta")[0]["t"]

        tarjetas = [
            ("Citas Registradas / Atendidas", f"{citas_reg} reg. / {citas_atend} atend.", "#1D4ED8"),
            ("Unidades Totales en Stock", f"{unidades_stock} und.", "#059669"),
            ("Cuentas Activas / Especialistas", f"{cuentas_activas} activas / {especialistas_cabina} esp.", "#7C3AED"),
            ("Ingresos por Ventas Directas", f"S/ {float(ventas_tot):.2f}", "#D97706"),
        ]

        for i, (titulo, valor, color) in enumerate(tarjetas):
            c = tk.Frame(kpi_frame, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=14)
            c.grid(row=0, column=i, sticky="nsew", padx=6)
            kpi_frame.columnconfigure(i, weight=1)
            tk.Label(c, text=titulo, font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_MUTED).pack(anchor="w")
            tk.Label(c, text=valor, font=("Segoe UI", 15, "bold"), bg=COLOR_CARD, fg=color).pack(anchor="w", pady=(6, 0))

        # Tabla resumen de próximas citas (filtradas por rol, T6)
        card_citas = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=14)
        card_citas.pack(fill=tk.BOTH, expand=True)

        titulo_tabla = (
            "📅 Agenda Global de Citas del Salón (Vista Administrador)"
            if sesion.es_admin
            else f"📅 Mis Citas Asignadas ({sesion.nombre})"
        )
        tk.Label(card_citas, text=titulo_tabla, font=("Segoe UI", 11, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 8))

        cols = ("num", "fecha", "inicio", "fin", "estado", "responsable", "servicio", "obs")
        tv = ttk.Treeview(card_citas, columns=cols, show="headings", height=12)
        for col, txt, w in [
            ("num", "N°", 50),
            ("fecha", "Fecha", 95),
            ("inicio", "Inicio", 75),
            ("fin", "Fin", 75),
            ("estado", "Estado", 100),
            ("responsable", "Responsable", 170),
            ("servicio", "Servicio(s)", 200),
            ("obs", "Cliente / Observaciones", 320),
        ]:
            tv.heading(col, text=txt)
            tv.column(col, width=w, anchor="w" if col in ("responsable", "servicio", "obs") else "center")
        tv.pack(fill=tk.BOTH, expand=True)

        filtro_sql = "" if sesion.es_admin else "WHERE c.id_usuario = %s"
        params_sql = () if sesion.es_admin else (sesion.id_usuario,)
        filas = self.db.consultar(
            f"""
            SELECT c.numero_registro, c.fecha, c.hora_inicio, c.hora_fin,
                   e.descripcion AS estado, u.nombre AS responsable,
                   GROUP_CONCAT(s.nombre SEPARATOR ', ') AS servicios,
                   COALESCE(c.observaciones, '') AS observaciones
              FROM cita c
              JOIN estado_cita e ON e.id_estado = c.id_estado
              JOIN usuario u ON u.id_usuario = c.id_usuario
              LEFT JOIN cita_servicio cs ON cs.numero_registro = c.numero_registro
              LEFT JOIN servicio s ON s.codigo_servicio = cs.codigo_servicio
              {filtro_sql}
             GROUP BY c.numero_registro, c.fecha, c.hora_inicio, c.hora_fin, e.descripcion, u.nombre, c.observaciones
             ORDER BY c.fecha DESC, c.hora_inicio DESC
            """,
            params_sql,
        )
        for f in filas:
            tv.insert(
                "",
                tk.END,
                values=(
                    f["numero_registro"],
                    f["fecha"],
                    f["hora_inicio"],
                    f["hora_fin"],
                    f["estado"],
                    f["responsable"],
                    f["servicios"] or "—",
                    f["observaciones"],
                ),
            )

    # ==================================================================
    # MÓDULO 2: AGENDA DE CITAS CON CONTROL DE HORARIO Y PROPIEDAD (T6, T7, T8)
    # ==================================================================
    def _modulo_citas(self) -> None:
        sesion = self.usuario_actual
        assert sesion is not None

        top_frame = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=12)
        top_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            top_frame,
            text="📅 Registro y Ciclo de Vida de Citas (`sp_registrar_cita` / `sp_cambiar_estado_cita`)",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 8))

        form = tk.Frame(top_frame, bg=COLOR_CARD)
        form.pack(fill=tk.X)

        tk.Label(form, text="Fecha (AAAA-MM-DD):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        var_fecha = tk.StringVar(value=dt.date.today().strftime("%Y-%m-%d"))
        tk.Entry(form, textvariable=var_fecha, width=14, font=("Segoe UI", 9)).grid(row=0, column=1, sticky="w", padx=4, pady=4)

        tk.Label(form, text="Hora Inicio (HH:MM):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=4, pady=4)
        var_hora = tk.StringVar(value="10:00")
        tk.Entry(form, textvariable=var_hora, width=10, font=("Segoe UI", 9)).grid(row=0, column=3, sticky="w", padx=4, pady=4)

        servicios = self.db.consultar("SELECT codigo_servicio, nombre, precio, duracion FROM servicio ORDER BY nombre")
        mapa_serv = {f"{s['nombre']} (S/ {s['precio']} - {s['duracion']} min)": int(s["codigo_servicio"]) for s in servicios}

        tk.Label(form, text="Servicio (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=4, sticky="w", padx=4, pady=4)
        var_serv = tk.StringVar(value=next(iter(mapa_serv.keys()), ""))
        ttk.Combobox(form, textvariable=var_serv, values=list(mapa_serv.keys()), state="readonly", width=34).grid(row=0, column=5, sticky="w", padx=4, pady=4)

        clientes = self.db.consultar("SELECT codigo_cliente, nombres, apellidos FROM cliente ORDER BY apellidos, nombres")
        lista_clientes = [f"{c['nombres']} {c['apellidos']}" for c in clientes]

        tk.Label(form, text="Cliente (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", padx=4, pady=4)
        var_cli = tk.StringVar(value=lista_clientes[0] if lista_clientes else "")
        ttk.Combobox(form, textvariable=var_cli, values=lista_clientes, state="readonly", width=26).grid(row=1, column=1, columnspan=2, sticky="w", padx=4, pady=4)

        tk.Label(form, text="Notas adicionales:", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=1, column=3, sticky="w", padx=4, pady=4)
        var_obs = tk.StringVar()
        tk.Entry(form, textvariable=var_obs, width=36, font=("Segoe UI", 9)).grid(row=1, column=4, columnspan=2, sticky="w", padx=4, pady=4)

        tabla_card = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=12)
        tabla_card.pack(fill=tk.BOTH, expand=True)

        cols = ("num", "fecha", "inicio", "fin", "estado", "responsable", "servicio", "obs")
        tv = ttk.Treeview(tabla_card, columns=cols, show="headings", height=11)
        for col, txt, w in [
            ("num", "N°", 50),
            ("fecha", "Fecha", 90),
            ("inicio", "Hora Inicio", 85),
            ("fin", "Hora Fin", 85),
            ("estado", "Estado", 105),
            ("responsable", "Responsable", 165),
            ("servicio", "Servicio", 190),
            ("obs", "Cliente y Observaciones (Límite del modelo: cliente en observaciones)", 330),
        ]:
            tv.heading(col, text=txt)
            tv.column(col, width=w, anchor="w" if col in ("responsable", "servicio", "obs") else "center")
        tv.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        def _cargar_citas() -> None:
            for item in tv.get_children():
                tv.delete(item)
            # T6: Un trabajador solo ve y cambia sus propias citas; sin casilla para ver todas
            filtro_w = "" if sesion.es_admin else "WHERE c.id_usuario = %s"
            params_w = () if sesion.es_admin else (sesion.id_usuario,)
            filas = self.db.consultar(
                f"""
                SELECT c.numero_registro, c.fecha, c.hora_inicio, c.hora_fin,
                       e.descripcion AS estado, u.nombre AS responsable,
                       GROUP_CONCAT(s.nombre SEPARATOR ', ') AS servicio,
                       COALESCE(c.observaciones, '') AS observaciones
                  FROM cita c
                  JOIN estado_cita e ON e.id_estado = c.id_estado
                  JOIN usuario u ON u.id_usuario = c.id_usuario
                  LEFT JOIN cita_servicio cs ON cs.numero_registro = c.numero_registro
                  LEFT JOIN servicio s ON s.codigo_servicio = cs.codigo_servicio
                  {filtro_w}
                 GROUP BY c.numero_registro, c.fecha, c.hora_inicio, c.hora_fin, e.descripcion, u.nombre, c.observaciones
                 ORDER BY c.fecha DESC, c.hora_inicio DESC
                """,
                params_w,
            )
            for f in filas:
                tv.insert(
                    "",
                    tk.END,
                    values=(
                        f["numero_registro"],
                        f["fecha"],
                        f["hora_inicio"],
                        f["hora_fin"],
                        f["estado"],
                        f["responsable"],
                        f["servicio"] or "—",
                        f["observaciones"],
                    ),
                )

        def _registrar_cita() -> None:
            cod_srv = mapa_serv.get(var_serv.get())
            if not cod_srv:
                messagebox.showwarning("Validación", "Seleccione un servicio del catálogo.")
                return
            try:
                num = self.db.registrar_cita_validada(
                    fecha=var_fecha.get().strip(),
                    hora_inicio=var_hora.get().strip(),
                    codigo_servicio=cod_srv,
                    observaciones=var_obs.get().strip(),
                    nombre_cliente=var_cli.get().strip(),
                )
                var_obs.set("")
                _cargar_citas()
                messagebox.showinfo("Cita Registrada", f"Cita #{num} registrada correctamente mediante sp_registrar_cita.")
            except Exception as err:
                messagebox.showerror("Regla de Negocio / Horario", str(err))

        tk.Button(
            form,
            text="➕ Registrar Cita (CALL sp_registrar_cita)",
            command=_registrar_cita,
            bg=COLOR_PRIMARY,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=14,
            pady=6,
        ).grid(row=1, column=6, padx=8, pady=4)

        acc_bar = tk.Frame(tabla_card, bg=COLOR_CARD)
        acc_bar.pack(fill=tk.X)

        tk.Label(acc_bar, text="Cambiar estado de la cita seleccionada a:", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        var_nuevo_est = tk.StringVar(value="Confirmada")
        ttk.Combobox(
            acc_bar,
            textvariable=var_nuevo_est,
            values=["Confirmada", "Atendida", "Cancelada"],
            state="readonly",
            width=16,
        ).pack(side=tk.LEFT, padx=4)

        def _cambiar_estado() -> None:
            sel = tv.selection()
            if not sel:
                messagebox.showwarning("Selección", "Seleccione una cita de la tabla.")
                return
            num_reg = int(tv.item(sel[0], "values")[0])
            try:
                self.db.cambiar_estado_cita_validado(num_reg, var_nuevo_est.get())
                _cargar_citas()
                messagebox.showinfo("Estado Actualizado", f"Cita #{num_reg} actualizada a '{var_nuevo_est.get()}'.")
            except Exception as err:
                messagebox.showerror("Ciclo de Vida de Cita (RN-04)", str(err))

        tk.Button(
            acc_bar,
            text="🔄 Aplicar Transición (`sp_cambiar_estado_cita`)",
            command=_cambiar_estado,
            bg=COLOR_SUCCESS,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=5,
        ).pack(side=tk.LEFT, padx=8)

        _cargar_citas()

    # ==================================================================
    # MÓDULO 3: CLIENTES Y PREFERENCIAS DE CATÁLOGO (T9: O11, O12)
    # ==================================================================
    def _modulo_clientes(self) -> None:
        top = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=12)
        top.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            top,
            text="👥 Registro de Clientes (`sp_registrar_cliente`) — Preferencias Exclusivas del Catálogo Oficial",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 8))

        form = tk.Frame(top, bg=COLOR_CARD)
        form.pack(fill=tk.X)

        tk.Label(form, text="Nombres (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        var_nom = tk.StringVar()
        tk.Entry(form, textvariable=var_nom, width=20, font=("Segoe UI", 9)).grid(row=0, column=1, padx=4, pady=4)

        tk.Label(form, text="Apellidos (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=4, pady=4)
        var_ape = tk.StringVar()
        tk.Entry(form, textvariable=var_ape, width=20, font=("Segoe UI", 9)).grid(row=0, column=3, padx=4, pady=4)

        tk.Label(form, text="Dirección / Calle:", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=4, sticky="w", padx=4, pady=4)
        var_calle = tk.StringVar()
        tk.Entry(form, textvariable=var_calle, width=22, font=("Segoe UI", 9)).grid(row=0, column=5, padx=4, pady=4)

        tk.Label(form, text="Distrito / Ciudad:", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", padx=4, pady=4)
        var_ciu = tk.StringVar(value="Miraflores")
        tk.Entry(form, textvariable=var_ciu, width=20, font=("Segoe UI", 9)).grid(row=1, column=1, padx=4, pady=4)

        prefs_catalogo = [""] + self.db.listar_preferencias_catalogo()
        tk.Label(form, text="Preferencia (Catálogo 3FN):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=1, column=2, sticky="w", padx=4, pady=4)
        var_pref = tk.StringVar(value=prefs_catalogo[1] if len(prefs_catalogo) > 1 else "")
        ttk.Combobox(form, textvariable=var_pref, values=prefs_catalogo, state="readonly", width=32).grid(row=1, column=3, columnspan=2, sticky="w", padx=4, pady=4)

        card_tabla = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=12)
        card_tabla.pack(fill=tk.BOTH, expand=True)

        cols = ("cod", "nombres", "apellidos", "calle", "ciudad", "preferencias", "registrado_por")
        tv = ttk.Treeview(card_tabla, columns=cols, show="headings", height=12)
        for col, txt, w in [
            ("cod", "Cód.", 55),
            ("nombres", "Nombres", 150),
            ("apellidos", "Apellidos", 160),
            ("calle", "Dirección / Calle", 190),
            ("ciudad", "Distrito / Ciudad", 140),
            ("preferencias", "Preferencias (Catálogo)", 240),
            ("registrado_por", "Atendido por", 160),
        ]:
            tv.heading(col, text=txt)
            tv.column(col, width=w, anchor="w" if col != "cod" else "center")
        tv.pack(fill=tk.BOTH, expand=True)

        def _cargar_clientes() -> None:
            for item in tv.get_children():
                tv.delete(item)
            filas = self.db.consultar(
                """
                SELECT c.codigo_cliente, c.nombres, c.apellidos,
                       COALESCE(c.calle, '—') AS calle,
                       COALESCE(c.ciudad, '—') AS ciudad,
                       COALESCE(GROUP_CONCAT(p.descripcion SEPARATOR ' / '), '—') AS preferencias,
                       u.nombre AS atendido_por
                  FROM cliente c
                  JOIN usuario u ON u.id_usuario = c.id_usuario
                  LEFT JOIN cliente_preferencia cp ON cp.codigo_cliente = c.codigo_cliente
                  LEFT JOIN preferencia p ON p.id_preferencia = cp.id_preferencia
                 GROUP BY c.codigo_cliente, c.nombres, c.apellidos, c.calle, c.ciudad, u.nombre
                 ORDER BY c.codigo_cliente DESC
                """
            )
            for f in filas:
                tv.insert(
                    "",
                    tk.END,
                    values=(
                        f["codigo_cliente"],
                        f["nombres"],
                        f["apellidos"],
                        f["calle"],
                        f["ciudad"],
                        f["preferencias"],
                        f["atendido_por"],
                    ),
                )

        def _guardar() -> None:
            try:
                cod = self.db.registrar_cliente_validado(
                    nombres=var_nom.get(),
                    apellidos=var_ape.get(),
                    calle=var_calle.get(),
                    ciudad=var_ciu.get(),
                    preferencia=var_pref.get(),
                )
                var_nom.set("")
                var_ape.set("")
                var_calle.set("")
                _cargar_clientes()
                messagebox.showinfo("Cliente Registrado", f"Cliente #{cod} registrado exitosamente mediante sp_registrar_cliente.")
            except Exception as err:
                messagebox.showerror("Error de Validación", str(err))

        tk.Button(
            form,
            text="➕ Registrar Cliente (`sp_registrar_cliente`)",
            command=_guardar,
            bg=COLOR_PRIMARY,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=14,
            pady=6,
        ).grid(row=1, column=5, padx=6, pady=4)

        _cargar_clientes()

    # ==================================================================
    # MÓDULO 4: VENTAS (CARRITO ATÓMICO T10) Y CONSUMO EN CABINA (T1)
    # ==================================================================
    def _modulo_ventas_inventario(self) -> None:
        top = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=12)
        top.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            top,
            text="🛒 Carrito de Venta Atómica (`sp_registrar_venta_carrito`) y Consumo en Cabina (`sp_descontar_botella_cabina`)",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 8))

        carrito: list[dict[str, int | str | float]] = []

        ctrl = tk.Frame(top, bg=COLOR_CARD)
        ctrl.pack(fill=tk.X)

        productos = self.db.consultar("SELECT codigo_producto, nombre, precio_unitario, stock FROM producto ORDER BY nombre")
        mapa_prod = {
            f"#{p['codigo_producto']} - {p['nombre']} (S/ {p['precio_unitario']} | Stock: {p['stock']})": p
            for p in productos
        }

        tk.Label(ctrl, text="Producto (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        var_prod = tk.StringVar(value=next(iter(mapa_prod.keys()), ""))
        cb_prod = ttk.Combobox(ctrl, textvariable=var_prod, values=list(mapa_prod.keys()), state="readonly", width=44)
        cb_prod.pack(side=tk.LEFT, padx=4)

        tk.Label(ctrl, text="Cantidad (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(8, 4))
        var_cant = tk.StringVar(value="1")
        tk.Entry(ctrl, textvariable=var_cant, width=7, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=4)

        lbl_carrito = tk.Label(top, text="Carrito actual: vacío", bg=COLOR_CARD, fg=COLOR_PRIMARY, font=("Segoe UI", 9, "bold"))
        lbl_carrito.pack(anchor="w", pady=(6, 0))

        def _actualizar_etiqueta_carrito() -> None:
            if not carrito:
                lbl_carrito.configure(text="Carrito actual: vacío")
            else:
                resumen = ", ".join(f"{c['cantidad']}x {c['nombre']}" for c in carrito)
                tot_est = sum(int(c["cantidad"]) * float(c["precio"]) for c in carrito)
                lbl_carrito.configure(text=f"Carrito ({len(carrito)} ítems): {resumen}  |  Total estimado: S/ {tot_est:.2f}")

        def _agregar_al_carrito() -> None:
            p = mapa_prod.get(var_prod.get())
            if not p:
                return
            try:
                c = int(var_cant.get().strip())
                if c <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Cantidad", "Ingrese una cantidad entera mayor a 0.")
                return
            carrito.append(
                {
                    "codigo_producto": int(p["codigo_producto"]),
                    "nombre": str(p["nombre"]),
                    "cantidad": c,
                    "precio": float(p["precio_unitario"]),
                }
            )
            _actualizar_etiqueta_carrito()

        def _confirmar_venta_carrito() -> None:
            if not carrito:
                _agregar_al_carrito()
            if not carrito:
                return
            try:
                if len(carrito) == 1:
                    item = carrito[0]
                    num_v, nom_p, tot = self.db.registrar_venta_atomica(int(item["codigo_producto"]), int(item["cantidad"]))
                    messagebox.showinfo("Venta Registrada", f"Venta #{num_v} ({nom_p}) por S/ {tot:.2f} registrada sin duplicar stock.")
                else:
                    lineas = [{"codigo_producto": int(i["codigo_producto"]), "cantidad": int(i["cantidad"])} for i in carrito]
                    num_v, tot = self.db.registrar_venta_carrito_atomica(lineas)
                    messagebox.showinfo("Carrito Vendido", f"Venta multiproducto #{num_v} registrada por S/ {tot:.2f}.")
                carrito.clear()
                self._abrir_modulo("ventas_inv")
            except Exception as err:
                messagebox.showerror("Error en Venta", str(err))

        def _descontar_cabina() -> None:
            p = mapa_prod.get(var_prod.get())
            if not p:
                return
            try:
                nom = self.db.descontar_botella_cabina_validada(int(p["codigo_producto"]))
                messagebox.showinfo("Consumo en Cabina", f"Se descontó 1 unidad agotada en cabina de '{nom}'.")
                self._abrir_modulo("ventas_inv")
            except Exception as err:
                messagebox.showerror("Error en Consumo de Cabina", str(err))

        tk.Button(
            ctrl,
            text="➕ Añadir al Carrito",
            command=_agregar_al_carrito,
            bg="#475569",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=10,
            pady=5,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            ctrl,
            text="✅ Confirmar Venta",
            command=_confirmar_venta_carrito,
            bg=COLOR_SUCCESS,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=5,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            ctrl,
            text="🧴 Descontar 1 Unidad Cabina",
            command=_descontar_cabina,
            bg=COLOR_WARNING,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=10,
            pady=5,
        ).pack(side=tk.LEFT, padx=4)

        card_inv = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=12)
        card_inv.pack(fill=tk.BOTH, expand=True)

        cols = ("cod", "nombre", "presentacion", "precio", "stock", "almacen")
        tv = ttk.Treeview(card_inv, columns=cols, show="headings", height=12)
        for col, txt, w in [
            ("cod", "Cód.", 55),
            ("nombre", "Producto", 240),
            ("presentacion", "Presentación", 200),
            ("precio", "Precio Unit.", 110),
            ("stock", "Stock Actual (Unidades)", 150),
            ("almacen", "Almacén Responsable", 180),
        ]:
            tv.heading(col, text=txt)
            tv.column(col, width=w, anchor="w" if col in ("nombre", "presentacion", "almacen") else "center")
        tv.pack(fill=tk.BOTH, expand=True)

        filas_p = self.db.consultar(
            """
            SELECT p.codigo_producto, p.nombre, COALESCE(p.descripcion, '—') AS descripcion,
                   p.precio_unitario, p.stock,
                   CONCAT('Almacén #', a.codigo_almacen, ' (', u.nombre, ')') AS almacen
              FROM producto p
              JOIN almacen a ON a.codigo_almacen = p.codigo_almacen
              JOIN usuario u ON u.id_usuario = a.id_usuario
             ORDER BY p.codigo_producto
            """
        )
        for fp in filas_p:
            tv.insert(
                "",
                tk.END,
                values=(
                    fp["codigo_producto"],
                    fp["nombre"],
                    fp["descripcion"],
                    f"S/ {float(fp['precio_unitario']):.2f}",
                    fp["stock"],
                    fp["almacen"],
                ),
            )

    # ==================================================================
    # MÓDULO 5: COMPRAS A PROVEEDORES (EXCLUSIVO ADMIN — T1, T6)
    # ==================================================================
    def _modulo_compras_admin(self) -> None:
        top = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=12)
        top.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            top,
            text="📦 Órdenes de Compra a Proveedores (`sp_registrar_pedido_compra` — Exclusivo ADMIN)",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 8))

        form = tk.Frame(top, bg=COLOR_CARD)
        form.pack(fill=tk.X)

        provs = self.db.consultar("SELECT codigo_proveedor, razon_social FROM proveedor ORDER BY razon_social")
        mapa_prov = {f"{p['razon_social']} (#{p['codigo_proveedor']})": int(p["codigo_proveedor"]) for p in provs}

        prods = self.db.consultar("SELECT codigo_producto, nombre, stock FROM producto ORDER BY nombre")
        mapa_prod = {f"{p['nombre']} (Stock: {p['stock']})": int(p["codigo_producto"]) for p in prods}

        tk.Label(form, text="Proveedor (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=4, pady=4, sticky="w")
        var_prov = tk.StringVar(value=next(iter(mapa_prov.keys()), ""))
        ttk.Combobox(form, textvariable=var_prov, values=list(mapa_prov.keys()), state="readonly", width=28).grid(row=0, column=1, padx=4, pady=4)

        tk.Label(form, text="Producto (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=2, padx=4, pady=4, sticky="w")
        var_prod = tk.StringVar(value=next(iter(mapa_prod.keys()), ""))
        ttk.Combobox(form, textvariable=var_prod, values=list(mapa_prod.keys()), state="readonly", width=30).grid(row=0, column=3, padx=4, pady=4)

        tk.Label(form, text="Cantidad (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=4, padx=4, pady=4, sticky="w")
        var_cant = tk.StringVar(value="10")
        tk.Entry(form, textvariable=var_cant, width=8).grid(row=0, column=5, padx=4, pady=4)

        tk.Label(form, text="Costo Unit. (S/) (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=6, padx=4, pady=4, sticky="w")
        var_costo = tk.StringVar(value="20.00")
        tk.Entry(form, textvariable=var_costo, width=10).grid(row=0, column=7, padx=4, pady=4)

        def _registrar_compra() -> None:
            try:
                id_ped = self.db.registrar_pedido_compra_atomico(
                    id_usuario_admin=None,
                    codigo_proveedor=mapa_prov[var_prov.get()],
                    codigo_producto=mapa_prod[var_prod.get()],
                    cantidad=int(var_cant.get().strip()),
                    costo_unitario=float(var_costo.get().strip()),
                )
                messagebox.showinfo("Pedido Registrado", f"Pedido de compra #{id_ped} registrado correctamente.")
                self._abrir_modulo("compras")
            except Exception as err:
                messagebox.showerror("Error en Pedido de Compra", str(err))

        tk.Button(
            form,
            text="➕ Emitir Orden (`sp_registrar_pedido_compra`)",
            command=_registrar_compra,
            bg=COLOR_PRIMARY,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=5,
        ).grid(row=0, column=8, padx=8, pady=4)

        card_ped = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=12)
        card_ped.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "fecha", "proveedor", "responsable", "producto", "cantidad", "costo")
        tv = ttk.Treeview(card_ped, columns=cols, show="headings", height=12)
        for col, txt, w in [
            ("id", "N° Pedido", 80),
            ("fecha", "Fecha", 100),
            ("proveedor", "Proveedor", 210),
            ("responsable", "Administrador", 180),
            ("producto", "Producto", 220),
            ("cantidad", "Cantidad", 90),
            ("costo", "Costo Unit.", 100),
        ]:
            tv.heading(col, text=txt)
            tv.column(col, width=w, anchor="w" if col in ("proveedor", "responsable", "producto") else "center")
        tv.pack(fill=tk.BOTH, expand=True)

        filas = self.db.consultar(
            """
            SELECT p.id_pedido, p.fecha, pr.razon_social, u.nombre AS admin,
                   prod.nombre AS producto, dp.cantidad, dp.precio
              FROM pedido_compra p
              JOIN proveedor pr ON pr.codigo_proveedor = p.codigo_proveedor
              JOIN usuario u ON u.id_usuario = p.id_usuario
              JOIN detalle_pedido dp ON dp.id_pedido = p.id_pedido
              JOIN producto prod ON prod.codigo_producto = dp.codigo_producto
             ORDER BY p.id_pedido DESC
            """
        )
        for f in filas:
            tv.insert(
                "",
                tk.END,
                values=(
                    f["id_pedido"],
                    f["fecha"],
                    f["razon_social"],
                    f["admin"],
                    f["producto"],
                    f["cantidad"],
                    f"S/ {float(f['precio']):.2f}",
                ),
            )

    # ==================================================================
    # MÓDULO 6: USUARIOS Y CREDENCIALES SIN MOSTRAR CONTRASEÑAS (T3, T4, T6)
    # ==================================================================
    def _modulo_usuarios_admin(self) -> None:
        top = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=12)
        top.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            top,
            text="🔐 Administración de Usuarios y Roles Explícitos (`spa_rodriguez_app.credencial` — Cero Contraseñas Visibles)",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 8))

        form = tk.Frame(top, bg=COLOR_CARD)
        form.pack(fill=tk.X)

        tk.Label(form, text="Nombre Completo (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        var_nom = tk.StringVar()
        tk.Entry(form, textvariable=var_nom, width=22).grid(row=0, column=1, padx=4, pady=4)

        tk.Label(form, text="Username (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=4, pady=4)
        var_usr = tk.StringVar()
        tk.Entry(form, textvariable=var_usr, width=16).grid(row=0, column=3, padx=4, pady=4)

        tk.Label(form, text="Teléfono (9 díg.):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=4, sticky="w", padx=4, pady=4)
        var_tel = tk.StringVar()
        tk.Entry(form, textvariable=var_tel, width=12).grid(row=0, column=5, padx=4, pady=4)

        tk.Label(form, text="Rol Explícito (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", padx=4, pady=4)
        var_rol = tk.StringVar(value=ROL_TRABAJADOR)
        ttk.Combobox(form, textvariable=var_rol, values=[ROL_TRABAJADOR, ROL_ADMIN], state="readonly", width=16).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        esps = self.db.listar_especialidades()
        tk.Label(form, text="Especialidad (Catálogo):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=1, column=2, sticky="w", padx=4, pady=4)
        var_esp = tk.StringVar(value=esps[0] if esps else "")
        ttk.Combobox(form, textvariable=var_esp, values=esps, state="readonly", width=24).grid(row=1, column=3, columnspan=2, sticky="w", padx=4, pady=4)

        card_tv = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=12)
        card_tv.pack(fill=tk.BOTH, expand=True)

        # Jamás se muestra contraseña ni hash (T3: O4)
        cols = ("id", "username", "nombre", "rol", "especialidad", "telefono", "estado_cuenta", "ultimo_acceso")
        tv = ttk.Treeview(card_tv, columns=cols, show="headings", height=11)
        for col, txt, w in [
            ("id", "ID", 45),
            ("username", "Username", 130),
            ("nombre", "Nombre del Operador", 200),
            ("rol", "Rol Explícito", 115),
            ("especialidad", "Especialidad (`empleado`)", 200),
            ("telefono", "Teléfono", 100),
            ("estado_cuenta", "Estado de Credencial", 160),
            ("ultimo_acceso", "Último Acceso", 145),
        ]:
            tv.heading(col, text=txt)
            tv.column(col, width=w, anchor="w" if col in ("username", "nombre", "especialidad") else "center")
        tv.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        def _cargar_usuarios() -> None:
            for item in tv.get_children():
                tv.delete(item)
            for u in self.db.obtener_usuarios_detallados():
                tv.insert(
                    "",
                    tk.END,
                    values=(
                        u["id_usuario"],
                        u["username"],
                        u["nombre"],
                        u["rol_codigo"],
                        u["especialidad_mostrar"],
                        u["telefono"] or "—",
                        u["estado_cuenta"],
                        str(u.get("ultimo_acceso") or "Nunca"),
                    ),
                )

        def _crear_usuario() -> None:
            try:
                uid, clave_temp = self.db.agregar_usuario(
                    nombre=var_nom.get(),
                    telefono=var_tel.get(),
                    rol=var_rol.get(),
                    especialidad=var_esp.get(),
                    username=var_usr.get(),
                )
                var_nom.set("")
                var_usr.set("")
                var_tel.set("")
                _cargar_usuarios()
                messagebox.showinfo(
                    "Usuario Creado (Clave Temporal de Un Solo Uso)",
                    f"Usuario ID #{uid} creado exitosamente.\n\n"
                    f"🔑 Contraseña temporal (entréguela ahora; no volverá a mostrarse):\n{clave_temp}\n\n"
                    "El operador deberá cambiarla obligatoriamente en su primer ingreso.",
                )
            except Exception as err:
                messagebox.showerror("Error al Crear Usuario", str(err))

        def _reset_clave() -> None:
            sel = tv.selection()
            if not sel:
                messagebox.showwarning("Selección", "Seleccione un usuario de la tabla.")
                return
            uid = int(tv.item(sel[0], "values")[0])
            uname = str(tv.item(sel[0], "values")[1])
            try:
                clave_temp = self.db.restablecer_contrasena_usuario(uid)
                _cargar_usuarios()
                messagebox.showinfo(
                    "Contraseña Temporal Generada",
                    f"Se restableció la credencial de '{uname}' (ID #{uid}).\n\n"
                    f"🔑 Nueva contraseña temporal (se muestra una única vez):\n{clave_temp}",
                )
            except Exception as err:
                messagebox.showerror("Error", str(err))

        tk.Button(
            form,
            text="➕ Crear Usuario con Clave Temporal",
            command=_crear_usuario,
            bg=COLOR_PRIMARY,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=5,
        ).grid(row=1, column=5, padx=6, pady=4)

        tk.Button(
            card_tv,
            text="🔑 Generar Nueva Clave Temporal (Un Solo Uso) al Usuario Seleccionado",
            command=_reset_clave,
            bg=COLOR_WARNING,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=14,
            pady=6,
        ).pack(anchor="w")

        _cargar_usuarios()

    # ==================================================================
    # MÓDULO 7: PROCEDIMIENTOS ALMACENADOS Y DICCIONARIO RN
    # ==================================================================
    def _modulo_procedimientos_almacenados(self) -> None:
        card = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=12)
        card.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            card,
            text="⚙️ Procedimientos Almacenados Precompilados en MySQL 8.0 (`SHOW CREATE PROCEDURE`)",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 8))

        rutinas = self.db.listar_procedimientos_almacenados()
        nombres = [r["nombre"] for r in rutinas]

        bar = tk.Frame(card, bg=COLOR_CARD)
        bar.pack(fill=tk.X, pady=(0, 8))
        tk.Label(bar, text="Seleccionar Procedimiento Almacenado:", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        var_sp = tk.StringVar(value=nombres[0] if nombres else "")
        cb = ttk.Combobox(bar, textvariable=var_sp, values=nombres, state="readonly", width=34)
        cb.pack(side=tk.LEFT, padx=4)

        txt = tk.Text(card, font=("Consolas", 9), bg="#0F172A", fg="#E2E8F0", height=22)
        txt.pack(fill=tk.BOTH, expand=True)

        def _mostrar_ddl(*_args) -> None:
            txt.delete("1.0", tk.END)
            sp = var_sp.get()
            if sp:
                ddl = self.db.obtener_ddl_procedimiento(sp)
                lineas_rn = "\n".join(f"--   {k}: {v}" for k, v in RN.items())
                txt.insert(tk.END, f"-- Diccionario Centralizado de Reglas de Negocio (config.RN):\n{lineas_rn}\n\n{ddl}")

        cb.bind("<<ComboboxSelected>>", _mostrar_ddl)
        _mostrar_ddl()

    # ==================================================================
    # MÓDULO 8: BITÁCORA PERSISTENTE (`spa_rodriguez_app.bitacora` — T11)
    # ==================================================================
    def _modulo_bitacora(self) -> None:
        card = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=16, pady=12)
        card.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            card,
            text="📜 Bitácora Persistente de Auditoría (`spa_rodriguez_app.bitacora`)",
            font=("Segoe UI", 11, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 8))

        cols = ("id", "fecha", "usuario", "accion", "detalle")
        tv = ttk.Treeview(card, columns=cols, show="headings", height=18)
        for col, txt, w in [
            ("id", "N°", 55),
            ("fecha", "Fecha y Hora", 150),
            ("usuario", "Username", 130),
            ("accion", "Acción", 180),
            ("detalle", "Detalle del Evento", 520),
        ]:
            tv.heading(col, text=txt)
            tv.column(col, width=w, anchor="w" if col in ("usuario", "accion", "detalle") else "center")
        tv.pack(fill=tk.BOTH, expand=True)

        for b in self.db.auth.consultar_bitacora(limite=200):
            tv.insert(
                "",
                tk.END,
                values=(b["id_bitacora"], b["fecha_hora"], b["username"], b["accion"], b["detalle"]),
            )

    # ==================================================================
    # MÓDULO 9: MI PERFIL Y CAMBIO DE CONTRASEÑA CON POLÍTICA (T3: O4)
    # ==================================================================
    def _modulo_perfil(self) -> None:
        sesion = self.usuario_actual
        assert sesion is not None

        card = tk.Frame(self.main_area, bg=COLOR_CARD, highlightbackground="#CBD5E1", highlightthickness=1, padx=24, pady=20)
        card.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            card,
            text=f"👤 Mi Perfil Operativo — {sesion.nombre}",
            font=("Segoe UI", 13, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 8))

        tk.Label(
            card,
            text=(
                f"• Username: {sesion.username}\n"
                f"• Rol Explícito: {sesion.rol} ({sesion.rol_etiqueta})\n"
                f"• Especialidad / Área: {sesion.especialidad}\n"
                "• Nota de Seguridad: Por política de seguridad, su contraseña nunca se muestra en pantalla."
            ),
            font=("Segoe UI", 10),
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
            justify="left",
        ).pack(anchor="w", pady=(0, 18))

        tk.Label(card, text="🔑 Cambiar Mi Contraseña", font=("Segoe UI", 11, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 8))

        form = tk.Frame(card, bg=COLOR_CARD)
        form.pack(anchor="w")

        tk.Label(form, text="Contraseña Actual (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=5)
        var_act = tk.StringVar()
        tk.Entry(form, textvariable=var_act, show="●", width=28).grid(row=0, column=1, padx=8, pady=5)

        tk.Label(form, text="Nueva Contraseña (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", pady=5)
        var_nva = tk.StringVar()
        tk.Entry(form, textvariable=var_nva, show="●", width=28).grid(row=1, column=1, padx=8, pady=5)

        tk.Label(form, text="Confirmar Nueva (*):", bg=COLOR_CARD, font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", pady=5)
        var_conf = tk.StringVar()
        tk.Entry(form, textvariable=var_conf, show="●", width=28).grid(row=2, column=1, padx=8, pady=5)

        def _guardar_clave() -> None:
            if var_nva.get() != var_conf.get():
                messagebox.showwarning("Validación", "La confirmación no coincide con la nueva contraseña.")
                return
            try:
                self.db.cambiar_contrasena_propia(var_act.get(), var_nva.get())
                var_act.set("")
                var_nva.set("")
                var_conf.set("")
                messagebox.showinfo("Éxito", "Su contraseña ha sido actualizada correctamente.")
            except Exception as err:
                messagebox.showerror("Error al Cambiar Contraseña", str(err))

        tk.Button(
            form,
            text="Guardar Nueva Contraseña",
            command=_guardar_clave,
            bg=COLOR_PRIMARY,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=14,
            pady=6,
        ).grid(row=3, column=1, sticky="w", padx=8, pady=10)
