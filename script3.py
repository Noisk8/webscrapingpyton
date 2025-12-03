import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import requests
import json
import threading
import webbrowser
import re

# =========================
# Configuración visual
# =========================

BG_COLOR = "#f3f4f6"
CARD_BG = "#ffffff"
CARD_BORDER = "#d1d5db"
ACCENT_COLOR = "#2563eb"
TEXT_MAIN = "#111827"
TEXT_MUTED = "#6b7280"
BADGE_GREEN = "#16a34a"
BADGE_RED = "#dc2626"
BADGE_YELLOW = "#f59e0b"

# =========================
# Configuración de datasets
# =========================

DATASETS = {
    "SECOP II - Procesos (p6dx-8zbt)": {
        "id": "p6dx-8zbt",
        "fields": [
            "Notice UID",
            "ID del proceso",
            "Referencia",
            "Entidad contratante",
            "NIT entidad",
            "Estado del procedimiento",
            "Adjudicado",
            "Proveedor adjudicado",
            "NIT proveedor",
            "Modalidad de contratación",
            "Tipo de contrato",
            "Objeto / descripción",
            "Descripción del contrato",
            "Valor del contrato",
            "Presupuesto base",
            "Duración",
            "Ubicación",
            "Fecha de publicación",
            "Fecha de adjudicación",
            "URL proceso",
        ],
        "currency_fields": {"Valor del contrato", "Presupuesto base"},
        "type": "procesos",
    },
    "SECOP II - Contratos electrónicos (jbjy-vk9h)": {
        "id": "jbjy-vk9h",
        "fields": [
            "Notice UID",
            "ID del proceso",
            "ID del contrato",
            "Referencia",
            "Entidad contratante",
            "NIT entidad",
            "Estado del contrato",
            "Adjudicado",
            "Proveedor adjudicado",
            "NIT proveedor",
            "Modalidad de contratación",
            "Tipo de contrato",
            "Objeto / descripción",
            "Descripción del contrato",
            "Valor del contrato",
            "Valor facturado",
            "Valor pagado",
            "Valor pendiente de pago",
            "Valor pago adelantado",
            "Duración",
            "Ubicación",
            "Fecha de firma",
            "Fecha de inicio",
            "Fecha de fin",
            "URL proceso",
        ],
        "currency_fields": {
            "Valor del contrato",
            "Valor facturado",
            "Valor pagado",
            "Valor pendiente de pago",
            "Valor pago adelantado",
        },
        "type": "contratos",
    },
}

# Dataset de proveedores registrados en SECOP II (Datos Abiertos)
PROVEEDORES_DATASET_ID = "qmzu-gj57"


# =========================
# Funciones de normalización
# =========================

def get_notice_uid(url: str) -> str | None:
    """Extrae noticeUID de la URL SECOP."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("noticeUID", "noticeUid", "noticeuid", "NoticeUID"):
        if params.get(key):
            return params[key][0]
    return None


def pick_first(row: dict, *keys):
    """Devuelve el primer valor no vacío de las claves indicadas."""
    for k in keys:
        val = row.get(k)
        if val not in (None, "", "NULL", "null"):
            return val
    return None


def format_plazo(row: dict) -> str | None:
    duracion = row.get("duracion")
    unidad = row.get("unidad_de_duracion")
    if duracion and unidad:
        return f"{duracion} {unidad}"
    if duracion:
        return str(duracion)
    return None


def format_ubicacion(row: dict) -> str | None:
    dep = row.get("departamento_entidad")
    ciudad = row.get("ciudad_entidad")
    parts = [p for p in [ciudad, dep] if p]
    return ", ".join(parts) if parts else None


def format_ubicacion_contrato(row: dict) -> str | None:
    dep = row.get("departamento")
    ciudad = row.get("ciudad")
    parts = [p for p in [ciudad, dep] if p]
    return ", ".join(parts) if parts else None


def normalize_proceso(row: dict, notice_uid: str) -> dict:
    """Mapea el registro crudo de Datos Abiertos a campos legibles (procesos)."""
    objeto = pick_first(row, "nombre_del_procedimiento", "descripci_n_del_procedimiento")
    descripcion = pick_first(row, "descripci_n_del_procedimiento", "nombre_del_procedimiento")
    valor = pick_first(row, "valor_total_adjudicacion", "precio_base")
    return {
        "Notice UID": notice_uid,
        "ID del proceso": row.get("id_del_proceso"),
        "Referencia": row.get("referencia_del_proceso"),
        "Entidad contratante": row.get("entidad"),
        "NIT entidad": row.get("nit_entidad"),
        "Estado del procedimiento": pick_first(
            row, "estado_del_procedimiento", "estado_resumen"
        ),
        "Adjudicado": row.get("adjudicado"),
        "Proveedor adjudicado": pick_first(
            row, "nombre_del_proveedor", "nombre_del_adjudicador"
        ),
        "NIT proveedor": row.get("nit_del_proveedor_adjudicado"),
        "Modalidad de contratación": row.get("modalidad_de_contratacion"),
        "Tipo de contrato": row.get("tipo_de_contrato"),
        "Objeto / descripción": objeto,
        "Descripción del contrato": descripcion,
        "Valor del contrato": valor,
        "Presupuesto base": row.get("precio_base"),
        "Duración": format_plazo(row),
        "Ubicación": format_ubicacion(row),
        "Fecha de publicación": row.get("fecha_de_publicacion_del"),
        "Fecha de adjudicación": row.get("fecha_adjudicacion"),
        "URL proceso": row.get("urlproceso", {}).get("url"),
    }


def normalize_contrato(row: dict, notice_uid: str) -> dict:
    """Normaliza registros del dataset de contratos electrónicos (jbjy-vk9h)."""
    return {
        "Notice UID": notice_uid,
        "ID del proceso": row.get("proceso_de_compra"),
        "ID del contrato": row.get("id_contrato"),
        "Referencia": row.get("referencia_del_contrato"),
        "Entidad contratante": row.get("nombre_entidad"),
        "NIT entidad": row.get("nit_entidad"),
        "Estado del contrato": row.get("estado_contrato"),
        "Adjudicado": row.get("adjudicado") or row.get("estado_contrato"),
        "Proveedor adjudicado": row.get("proveedor_adjudicado"),
        "NIT proveedor": row.get("documento_proveedor"),
        "Modalidad de contratación": row.get("modalidad_de_contratacion"),
        "Tipo de contrato": row.get("tipo_de_contrato"),
        "Objeto / descripción": pick_first(
            row, "objeto_del_contrato", "descripcion_del_proceso"
        ),
        "Descripción del contrato": pick_first(
            row, "descripcion_del_proceso", "objeto_del_contrato"
        ),
        "Valor del contrato": row.get("valor_del_contrato"),
        "Valor facturado": row.get("valor_facturado"),
        "Valor pagado": row.get("valor_pagado"),
        "Valor pendiente de pago": row.get("valor_pendiente_de_pago"),
        "Valor pago adelantado": row.get("valor_de_pago_adelantado"),
        "Duración": row.get("duraci_n_del_contrato"),
        "Ubicación": format_ubicacion_contrato(row),
        "Fecha de firma": row.get("fecha_de_firma"),
        "Fecha de inicio": row.get("fecha_de_inicio_del_contrato"),
        "Fecha de fin": row.get("fecha_de_fin_del_contrato"),
        "URL proceso": row.get("urlproceso", {}).get("url"),
    }


def _extract_notice_from_row(row: dict) -> str:
    """Intenta extraer noticeUID desde urlproceso.url en la fila."""
    url = None
    try:
        url = row.get("urlproceso", {}).get("url")
    except Exception:
        url = None
    if not url:
        return "No disponible"
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("noticeUID", "noticeUid", "noticeuid", "NoticeUID"):
        if params.get(key):
            return params[key][0]
    return "No disponible"


# =========================
# Funciones de consulta
# =========================

def fetch_from_open_data(url: str, dataset_key: str) -> dict:
    """
    Consulta Datos Abiertos con el noticeUID extraído de la URL
    usando el dataset seleccionado.
    Retorna un diccionario listo para mostrar.
    """
    if dataset_key not in DATASETS:
        raise ValueError("Dataset no soportado.")

    notice_uid = get_notice_uid(url)
    if not notice_uid:
        raise ValueError("No se encontró noticeUID en la URL SECOP.")

    ds = DATASETS[dataset_key]
    endpoint = f"https://www.datos.gov.co/resource/{ds['id']}.json"

    params = {
        "$limit": 1,
        "$where": f"upper(urlproceso.url) like upper('%{notice_uid}%')",
    }

    resp = requests.get(endpoint, params=params, timeout=20)
    resp.raise_for_status()
    rows = resp.json()

    if not rows:
        raise RuntimeError(
            "No se encontró el proceso/contrato en Datos Abiertos.\n"
            "Asegúrate de que el noticeUID exista o intenta más tarde."
        )

    if ds["type"] == "procesos":
        record = normalize_proceso(rows[0], notice_uid)
    elif ds["type"] == "contratos":
        record = normalize_contrato(rows[0], notice_uid)
    else:
        raise ValueError("Tipo de dataset no soportado.")

    # Limpieza básica
    for k, v in record.items():
        if isinstance(v, str):
            record[k] = v.strip()
        if record[k] in ("", None):
            record[k] = "No disponible"
    record["Consultado"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return record


def fetch_by_keyword(term: str, dataset_key: str, limit: int = 25) -> list[dict]:
    """Busca por palabra clave en campos relevantes y devuelve múltiples registros normalizados."""
    if dataset_key not in DATASETS:
        raise ValueError("Dataset no soportado.")
    term = term.strip()
    if not term:
        raise ValueError("Debes ingresar una palabra clave.")

    ds = DATASETS[dataset_key]
    endpoint = f"https://www.datos.gov.co/resource/{ds['id']}.json"
    like_pattern = term.replace("'", "''")

    if ds["type"] == "procesos":
        cols = [
            "nombre_del_procedimiento",
            "descripci_n_del_procedimiento",
            "entidad",
            "referencia_del_proceso",
            "id_del_proceso",
        ]
    else:
        cols = [
            "objeto_del_contrato",
            "descripcion_del_proceso",
            "nombre_entidad",
            "proveedor_adjudicado",
            "referencia_del_contrato",
            "id_contrato",
        ]

    where_clause = " OR ".join(
        [f"upper({c}) like upper('%{like_pattern}%')" for c in cols]
    )

    params = {"$limit": limit, "$where": where_clause}
    resp = requests.get(endpoint, params=params, timeout=20)
    resp.raise_for_status()
    rows = resp.json()

    if not rows:
        return []

    records = []
    for row in rows:
        notice = _extract_notice_from_row(row)
        if ds["type"] == "procesos":
            record = normalize_proceso(row, notice)
        else:
            record = normalize_contrato(row, notice)
        for k, v in record.items():
            if isinstance(v, str):
                record[k] = v.strip()
            if record[k] in ("", None):
                record[k] = "No disponible"
        records.append(record)

    return records


def fetch_proveedor_por_nit(nit: str) -> dict | None:
    """
    Consulta Datos Abiertos (SECOP II – Proveedores Registrados)
    por NIT y devuelve la fila cruda.
    """
    nit_clean = re.sub(r"\D", "", str(nit or ""))
    if not nit_clean:
        return None

    endpoint = f"https://www.datos.gov.co/resource/{PROVEEDORES_DATASET_ID}.json"
    params = {"$limit": 1, "nit": nit_clean}

    try:
        resp = requests.get(endpoint, params=params, timeout=15)
        resp.raise_for_status()
        rows = resp.json()
    except Exception:
        return None

    if not rows:
        return None

    return rows[0]


# =========================
# Interfaz gráfica moderna
# =========================

class SecopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Analizador SECOP (Datos Abiertos)")
        self.geometry("1100x750")
        self.configure(bg=BG_COLOR)

        self.url_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="url")  # url o keyword
        self.dataset_var = tk.StringVar(value=list(DATASETS.keys())[0])
        self.status_var = tk.StringVar(value="Listo")
        self.results_header_var = tk.StringVar(value="Sin resultados aún.")
        self.last_record = None
        self.records = []
        self.last_query = ""
        self.last_mode = "url"

        self._build_ui()

    # ---------- UI base ----------

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Estilos globales
        style.configure("TFrame", background=BG_COLOR)
        style.configure("TLabel", background=BG_COLOR, foreground=TEXT_MAIN, font=("Segoe UI", 10))
        style.configure("Heading.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Subheading.TLabel", font=("Segoe UI", 10), foreground=TEXT_MUTED)
        style.configure("Hint.TLabel", font=("Segoe UI", 9), foreground=TEXT_MUTED)

        style.configure(
            "Header.TFrame",
            background=CARD_BG,
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "Card.TFrame",
            background=CARD_BG,
            relief="solid",
            borderwidth=1,
        )
        # Frame interno sin bordes (para que no se vea "recuadrado" todo)
        style.configure(
            "CardInner.TFrame",
            background=CARD_BG,
            relief="flat",
            borderwidth=0,
        )

        style.configure(
            "ResultTitle.TLabel",
            background=CARD_BG,
            foreground=TEXT_MUTED,
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "FieldLabel.TLabel",
            background=CARD_BG,
            foreground=TEXT_MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "FieldValue.TLabel",
            background=CARD_BG,
            foreground=TEXT_MAIN,
            font=("Segoe UI", 9),
        )

        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.map(
            "Accent.TButton",
            foreground=[("active", "white"), ("!disabled", "white")],
            background=[("active", ACCENT_COLOR), ("!disabled", ACCENT_COLOR)],
        )

        container = ttk.Frame(self, padding=12)
        container.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(3, weight=1)  # Expande la sección de resultados

        # Header
        header = ttk.Frame(container, style="Header.TFrame", padding=(16, 12))
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(
            header,
            text="📑 Analizador SECOP (Datos Abiertos)",
            style="Heading.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Explora procesos y contratos de SECOP II desde Datos Abiertos Colombia.",
            style="Subheading.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        # Card de búsqueda
        search_card = ttk.Frame(container, style="Card.TFrame", padding=(16, 12))
        search_card.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        search_card.columnconfigure(1, weight=1)

        # Fila 0: etiqueta + entry + botón
        ttk.Label(search_card, text="Buscar", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        entry = ttk.Entry(search_card, textvariable=self.url_var)
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        entry.insert(0, "URL de detalle SECOP II o palabra clave…")
        entry.bind("<FocusIn>", self._clear_placeholder)

        btn_search = ttk.Button(
            search_card,
            text="Buscar",
            style="Accent.TButton",
            command=self.on_analyze,
        )
        btn_search.grid(row=0, column=2, sticky="e")

        # Fila 1: modo de búsqueda + dataset
        mode_frame = ttk.Frame(search_card, style="CardInner.TFrame")
        mode_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        mode_frame.columnconfigure(3, weight=1)

        ttk.Label(mode_frame, text="Modo de búsqueda:", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky="w"
        )

        url_radio = ttk.Radiobutton(
            mode_frame,
            text="URL / noticeUID",
            variable=self.mode_var,
            value="url",
        )
        url_radio.grid(row=0, column=1, padx=(8, 0))

        kw_radio = ttk.Radiobutton(
            mode_frame,
            text="Palabra clave",
            variable=self.mode_var,
            value="keyword",
        )
        kw_radio.grid(row=0, column=2, padx=(8, 0))

        ttk.Label(mode_frame, text="Fuente de datos:", style="FieldLabel.TLabel").grid(
            row=0, column=3, sticky="e", padx=(16, 4)
        )
        ds_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.dataset_var,
            values=list(DATASETS.keys()),
            state="readonly",
            width=45,
        )
        ds_combo.grid(row=0, column=4, sticky="e")

        # Fila 2: botones pequeños y estado
        actions = ttk.Frame(search_card, style="CardInner.TFrame")
        actions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        actions.columnconfigure(2, weight=1)

        ttk.Button(actions, text="🖫 Guardar JSON", command=self.on_save).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(actions, text="🧹 Limpiar", command=self.on_clear).grid(
            row=0, column=1, padx=(0, 6)
        )

        ttk.Label(actions, text="Estado:", style="Hint.TLabel").grid(
            row=0, column=2, sticky="e", padx=(0, 4)
        )
        self.status_label = ttk.Label(actions, textvariable=self.status_var, style="Hint.TLabel")
        self.status_label.grid(row=0, column=3, sticky="w")
        self.progress = ttk.Progressbar(actions, mode="indeterminate", length=160)
        self.progress.grid(row=0, column=4, sticky="e", padx=(12, 0))

        # Header de resultados
        results_header = ttk.Label(
            container, textvariable=self.results_header_var, style="Subheading.TLabel"
        )
        results_header.grid(row=2, column=0, sticky="w", pady=(4, 4))

        # Contenedor scrollable de resultados (cards)
        results_container = ttk.Frame(container)
        results_container.grid(row=3, column=0, sticky="nsew")
        results_container.rowconfigure(0, weight=1)
        results_container.columnconfigure(0, weight=1)

        self.results_canvas = tk.Canvas(
            results_container,
            background=BG_COLOR,
            highlightthickness=0,
        )
        self.results_canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            results_container, orient="vertical", command=self.results_canvas.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.results_canvas.configure(yscrollcommand=scrollbar.set)

        self.results_frame = ttk.Frame(self.results_canvas, style="TFrame")
        self.results_window = self.results_canvas.create_window(
            (0, 0), window=self.results_frame, anchor="nw"
        )
        self.results_frame.bind(
            "<Configure>",
            lambda e: self.results_canvas.configure(
                scrollregion=self.results_canvas.bbox("all")
            ),
        )
        self.results_canvas.bind(
            "<Configure>",
            lambda e: self.results_canvas.itemconfig(
                self.results_window, width=e.width
            ),
        )

        # Scroll con la rueda del ratón (Windows/macOS)
        self.results_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        # Scroll con rueda en Linux (Button-4/5)
        self.results_canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.results_canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

        # Texto de ayuda
        ttk.Label(
            container,
            text="Esta herramienta usa Datos Abiertos de SECOP (p6dx-8zbt, jbjy-vk9h, qmzu-gj57). "
                 "Puedes buscar por URL/noticeUID (detalle SECOP) o por palabra clave (ej. 'policía').",
            style="Hint.TLabel",
            wraplength=900,
        ).grid(row=4, column=0, sticky="w", pady=(6, 0))

    # ---------- Interacciones ----------

    def _clear_placeholder(self, event):
        if self.url_var.get() == "URL de detalle SECOP II o palabra clave…":
            self.url_var.set("")

    def on_analyze(self):
        query = self.url_var.get().strip()
        if not query or query == "URL de detalle SECOP II o palabra clave…":
            messagebox.showwarning(
                "Falta dato",
                "Ingresa una URL (modo URL) o una palabra clave (modo keyword).",
            )
            return

        self.status_var.set("Consultando...")
        self._show_loader()
        self._set_controls_state("disabled")

        self.last_query = query
        self.last_mode = self.mode_var.get()

        thread = threading.Thread(
            target=self._run_fetch,
            args=(query, self.dataset_var.get(), self.mode_var.get()),
            daemon=True,
        )
        thread.start()

    def _run_fetch(self, query, dataset_key, mode):
        """Ejecuta la consulta en background y actualiza la UI al finalizar."""
        try:
            if mode == "keyword":
                records = fetch_by_keyword(query, dataset_key)
                if not records:
                    raise RuntimeError("No se encontraron resultados para ese término.")
            else:
                record = fetch_from_open_data(query, dataset_key)
                records = [record]

            self.records = records
            self.last_record = records[0] if records else None

            self.after(0, lambda: self._render_records(records, dataset_key))
            self.after(0, lambda: self.status_var.set("Listo"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error al analizar", str(e)))
            self.after(0, lambda: self.status_var.set("Error"))
        finally:
            self.after(0, self._hide_loader)
            self.after(0, lambda: self._set_controls_state("normal"))

    # ---------- Render de resultados (cards) ----------

    def _render_records(self, records, dataset_key):
        # Limpiar cards anteriores
        for child in self.results_frame.winfo_children():
            child.destroy()

        if not records:
            self.results_header_var.set("Sin resultados.")
            return

        if self.last_mode == "keyword":
            header = f'Resultados para "{self.last_query}" en {dataset_key} ({len(records)})'
        else:
            header = f"Resultado para URL/noticeUID en {dataset_key} ({len(records)})"

        self.results_header_var.set(header)

        ds = DATASETS[dataset_key]
        for idx, record in enumerate(records, start=1):
            self._create_result_card(self.results_frame, record, idx, ds["type"])

    def _create_result_card(self, parent, record: dict, index: int, ds_type: str):
        card = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
        card.grid(row=index - 1, column=0, sticky="ew", pady=(0, 10))
        parent.columnconfigure(0, weight=1)

        # Header: resultado + badge de estado
        header_frame = ttk.Frame(card, style="CardInner.TFrame")
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(
            header_frame,
            text=f"RESULTADO #{index}",
            style="ResultTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")

        status_text = record.get("Estado del contrato") or record.get(
            "Estado del procedimiento"
        ) or record.get("Adjudicado") or "Sin estado"
        status_color = self._status_color(status_text)

        status_badge = tk.Label(
            header_frame,
            text=f"  ● {status_text}  ",
            bg=status_color,
            fg="white",
            font=("Segoe UI", 9, "bold"),
        )
        status_badge.grid(row=0, column=1, sticky="e")

        # Entidad y proveedor
        row1 = ttk.Frame(card, style="CardInner.TFrame")
        row1.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(row1, text="Entidad contratante:", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            row1,
            text=record.get("Entidad contratante", "No disponible"),
            style="FieldValue.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=(4, 0))

        ttk.Label(row1, text="Proveedor adjudicado:", style="FieldLabel.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 0)
        )
        ttk.Label(
            row1,
            text=record.get("Proveedor adjudicado", "No disponible"),
            style="FieldValue.TLabel",
        ).grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(2, 0))

        # Objeto / descripción
        row2 = ttk.Frame(card, style="CardInner.TFrame")
        row2.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(row2, text="Objeto / descripción", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        objeto = record.get("Objeto / descripción", "No disponible")
        if isinstance(objeto, str) and len(objeto) > 260:
            objeto_short = objeto[:260].rstrip() + "..."
        else:
            objeto_short = objeto
        ttk.Label(
            row2,
            text=objeto_short,
            style="FieldValue.TLabel",
            wraplength=900,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Métricas clave (dos columnas)
        metrics = ttk.Frame(card, style="CardInner.TFrame")
        metrics.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        metrics.columnconfigure(0, weight=1)
        metrics.columnconfigure(1, weight=1)

        # Columna izquierda
        left = ttk.Frame(metrics, style="CardInner.TFrame")
        left.grid(row=0, column=0, sticky="nw")
        valor_str = self._format_currency(record.get("Valor del contrato"))
        self._metric_row(left, "Valor del contrato:", valor_str, 0)
        self._metric_row(
            left,
            "Modalidad:",
            record.get("Modalidad de contratación", "No disponible"),
            1,
        )
        self._metric_row(
            left,
            "Tipo de contrato:",
            record.get("Tipo de contrato", "No disponible"),
            2,
        )

        # Columna derecha
        right = ttk.Frame(metrics, style="CardInner.TFrame")
        right.grid(row=0, column=1, sticky="nw")
        date_keys = [
            ("Fecha de firma", "Firma:"),
            ("Fecha de publicación", "Publicación:"),
            ("Fecha de adjudicación", "Adjudicación:"),
            ("Fecha de inicio", "Inicio:"),
            ("Fecha de fin", "Fin:"),
        ]
        r = 0
        for key, label in date_keys:
            val = record.get(key)
            if val and val != "No disponible":
                self._metric_row(right, f"{label}", val, r)
                r += 1
        # Ubicación
        ubic = record.get("Ubicación")
        if ubic and ubic != "No disponible":
            self._metric_row(right, "Ubicación:", ubic, r)

        # Identificadores + NIT + link SECOP
        footer = ttk.Frame(card, style="CardInner.TFrame")
        footer.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(0, weight=1)
        footer.columnconfigure(1, weight=0)

        ids_text = []
        for k in ("Notice UID", "ID del proceso", "ID del contrato"):
            val = record.get(k)
            if val and val != "No disponible":
                ids_text.append(f"{k}: {val}")
        ttk.Label(
            footer,
            text="   ".join(ids_text),
            style="Hint.TLabel",
        ).grid(row=0, column=0, sticky="w")

        # NIT entidad / proveedor (clicables)
        nit_frame = ttk.Frame(footer, style="CardInner.TFrame")
        nit_frame.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self._nit_link(
            nit_frame,
            "NIT entidad:",
            record.get("NIT entidad", "No disponible"),
            0,
        )
        self._nit_link(
            nit_frame,
            "NIT proveedor:",
            record.get("NIT proveedor", "No disponible"),
            1,
        )

        # Botón abrir proceso SECOP
        url = record.get("URL proceso")
        if url and url != "No disponible":
            btn = ttk.Button(
                footer,
                text="🔗 Abrir proceso en SECOP",
                command=lambda link=url: webbrowser.open_new_tab(link),
            )
            btn.grid(row=1, column=1, sticky="e", padx=(12, 0))

    def _metric_row(self, parent, label, value, row):
        ttk.Label(parent, text=label, style="FieldLabel.TLabel").grid(
            row=row, column=0, sticky="w"
        )
        ttk.Label(parent, text=value or "No disponible", style="FieldValue.TLabel").grid(
            row=row, column=1, sticky="w", padx=(4, 0)
        )

    def _status_color(self, status: str) -> str:
        s = (status or "").lower()
        if any(w in s for w in ("terminado", "celebrado", "ejecutado", "adjudicado", "seleccionado")):
            return BADGE_GREEN
        if any(w in s for w in ("en tramite", "proceso", "publicado", "presentaci")):
            return BADGE_YELLOW
        if any(w in s for w in ("cancelado", "desierto", "revocado")):
            return BADGE_RED
        return BADGE_YELLOW

    # ---------- NIT / proveedores ----------

    def _nit_link(self, parent, label_text: str, nit_value: str, row: int):
        ttk.Label(parent, text=label_text, style="FieldLabel.TLabel").grid(
            row=row, column=0, sticky="w"
        )
        if nit_value and nit_value != "No disponible":
            nit_clean = re.sub(r"\D", "", str(nit_value))
        else:
            nit_clean = ""

        if nit_clean:
            link = tk.Label(
                parent,
                text=nit_value,
                fg=ACCENT_COLOR,
                cursor="hand2",
                font=("Segoe UI", 9, "underline"),
                bg=CARD_BG,
            )
            link.grid(row=row, column=1, sticky="w", padx=(4, 0))
            link.bind(
                "<Button-1>",
                lambda e, n=nit_clean: self._open_proveedor_dialog(n),
            )
        else:
            ttk.Label(parent, text="No disponible", style="FieldValue.TLabel").grid(
                row=row, column=1, sticky="w", padx=(4, 0)
            )

    def _open_proveedor_dialog(self, nit: str):
        """Abre una ventana con los datos del proveedor desde Datos Abiertos."""
        row = fetch_proveedor_por_nit(nit)
        if not row:
            messagebox.showinfo(
                "Proveedor no encontrado",
                f"No se encontró información de proveedor en Datos Abiertos para el NIT {nit}.",
            )
            return

        top = tk.Toplevel(self)
        top.title(f"Proveedor SECOP II – NIT {nit}")
        top.configure(bg=BG_COLOR)
        top.geometry("500x400")

        style = ttk.Style(top)
        style.configure("ProvCard.TFrame", background=CARD_BG, relief="solid", borderwidth=1)
        style.configure("ProvInner.TFrame", background=CARD_BG, relief="flat", borderwidth=0)
        style.configure("ProvTitle.TLabel", background=CARD_BG, foreground=TEXT_MAIN,
                        font=("Segoe UI", 11, "bold"))
        style.configure("ProvField.TLabel", background=CARD_BG, foreground=TEXT_MUTED,
                        font=("Segoe UI", 9))
        style.configure("ProvValue.TLabel", background=CARD_BG, foreground=TEXT_MAIN,
                        font=("Segoe UI", 9))

        container = ttk.Frame(top, padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        card = ttk.Frame(container, style="ProvCard.TFrame", padding=(16, 12))
        card.grid(row=0, column=0, sticky="nsew")
        card.columnconfigure(1, weight=1)

        ttk.Label(
            card,
            text=f"Proveedor registrado en SECOP II",
            style="ProvTitle.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Mostrar algunos campos "bonitos" primero si existen
        def get_any(key_candidates):
            for k in row.keys():
                for cand in key_candidates:
                    if k.lower() == cand:
                        return row.get(k)
            return None

        nombre = get_any(["nombre", "nombre_proveedor"])
        ubicacion = get_any(["ubicacion", "ubicaci_n"])
        tipo_empresa = get_any(["tipo_empresa", "tipo_de_empresa"])
        es_pyme = get_any(["espyme", "es_pyme"])
        departamento = get_any(["departamento"])
        municipio = get_any(["municipio"])
        fecha_creacion = get_any(["fecha_creacion", "fecha_de_creacion", "fecha_registro"])
        pais = get_any(["pais"])

        pretty = [
            ("NIT", nit),
            ("Nombre", nombre),
            ("Tipo de empresa", tipo_empresa),
            ("Es PyME", es_pyme),
            ("Ubicación", ubicacion),
            ("País", pais),
            ("Departamento", departamento),
            ("Municipio", municipio),
            ("Fecha de creación", fecha_creacion),
        ]

        row_idx = 1
        for label, value in pretty:
            if not value:
                continue
            ttk.Label(card, text=f"{label}:", style="ProvField.TLabel").grid(
                row=row_idx, column=0, sticky="nw", pady=(2, 0)
            )
            ttk.Label(card, text=str(value), style="ProvValue.TLabel", wraplength=360).grid(
                row=row_idx, column=1, sticky="nw", pady=(2, 0), padx=(4, 0)
            )
            row_idx += 1

        # Separador
        ttk.Separator(card, orient="horizontal").grid(
            row=row_idx, column=0, columnspan=2, sticky="ew", pady=(8, 4)
        )
        row_idx += 1

        # Mostrar el resto de campos crudos para transparencia
        ttk.Label(
            card,
            text="Campos del dataset:",
            style="ProvField.TLabel",
        ).grid(row=row_idx, column=0, columnspan=2, sticky="w")
        row_idx += 1

        for k, v in row.items():
            if k.startswith(":"):
                continue  # metadatos de Socrata
            if k.lower() in ("nit",):
                continue  # ya mostrado
            label = k.replace("_", " ").title()
            ttk.Label(card, text=f"{label}:", style="ProvField.TLabel").grid(
                row=row_idx, column=0, sticky="nw"
            )
            ttk.Label(card, text=str(v), style="ProvValue.TLabel", wraplength=360).grid(
                row=row_idx, column=1, sticky="nw", padx=(4, 0)
            )
            row_idx += 1

    # ---------- Scroll ----------

    def _on_mousewheel(self, event):
        # Windows/macOS
        self.results_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        # Linux (event.num 4 = arriba, 5 = abajo)
        if event.num == 4:
            self.results_canvas.yview_scroll(-3, "units")
        elif event.num == 5:
            self.results_canvas.yview_scroll(3, "units")

    # ---------- Utilidades ----------

    def _format_currency(self, value):
        """Formatea valores a pesos colombianos con separadores de miles."""
        if value in (None, "No disponible"):
            return "No disponible"
        try:
            num = float(str(value).replace(",", "").replace(" ", ""))
            return f"${num:,.0f} COP"
        except Exception:
            return str(value)

    def on_save(self):
        """Guarda el primer resultado en JSON."""
        if not self.last_record:
            messagebox.showwarning("Sin datos", "No hay resultados para descargar.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
            title="Guardar consulta",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.last_record, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Guardado", f"Consulta guardada en:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {e}")

    def on_clear(self):
        """Limpia búsqueda y resultados."""
        self.url_var.set("")
        self.status_var.set("Listo")
        self.results_header_var.set("Sin resultados aún.")
        self.last_record = None
        self.records = []
        for child in self.results_frame.winfo_children():
            child.destroy()
        self._hide_loader()
        self._set_controls_state("normal")

    def _set_controls_state(self, state):
        """Habilita o deshabilita controles mientras carga."""
        for child in self.winfo_children():
            self._toggle_state_recursive(child, state)

    def _toggle_state_recursive(self, widget, state):
        if isinstance(widget, (ttk.Button, ttk.Entry, ttk.Combobox, ttk.Radiobutton)):
            try:
                widget.state([state] if state == "disabled" else ["!disabled"])
            except Exception:
                try:
                    widget.configure(state=state)
                except Exception:
                    pass
        for child in widget.winfo_children():
            self._toggle_state_recursive(child, state)

    def _show_loader(self):
        self.progress.start(10)

    def _hide_loader(self):
        self.progress.stop()


if __name__ == "__main__":
    app = SecopApp()
    app.mainloop()
