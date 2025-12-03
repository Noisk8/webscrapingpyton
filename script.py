import tkinter as tk
from tkinter import ttk, messagebox
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import requests
import json
from tkinter import filedialog

# Endpoint de Datos Abiertos (SECOP II - Procesos)
# Fuente: https://www.datos.gov.co/resource/p6dx-8zbt.json
API_ENDPOINT = "https://www.datos.gov.co/resource/p6dx-8zbt.json"

# Orden de campos a mostrar en la UI
FIELDS_ORDER = [
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
]


def get_notice_uid(url: str) -> str | None:
    """Extrae noticeUID de la URL."""
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


def normalize_record(row: dict, notice_uid: str) -> dict:
    """Mapea el registro crudo de Datos Abiertos a campos legibles."""
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


def fetch_from_open_data(url: str) -> dict:
    """
    Consulta Datos Abiertos de SECOP II con el noticeUID extraído de la URL.
    Retorna un diccionario listo para mostrar.
    """
    notice_uid = get_notice_uid(url)
    if not notice_uid:
        raise ValueError("No se encontró noticeUID en la URL.")

    params = {
        "$limit": 1,
        "$where": f"upper(urlproceso.url) like upper('%{notice_uid}%')",
    }

    resp = requests.get(API_ENDPOINT, params=params, timeout=20)
    resp.raise_for_status()
    rows = resp.json()

    if not rows:
        raise RuntimeError(
            "No se encontró el proceso en Datos Abiertos SECOP II.\n"
            "Asegúrate de que el noticeUID exista o intenta más tarde."
        )

    record = normalize_record(rows[0], notice_uid)
    # Limpieza básica
    for k, v in record.items():
        if isinstance(v, str):
            record[k] = v.strip()
        if record[k] in ("", None):
            record[k] = "No disponible"
    record["Consultado"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return record


class SecopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Analizador SECOP II (Datos Abiertos)")
        self.geometry("900x700")
        self.url_var = tk.StringVar()
        self.last_record = None
        self._build_ui()

    def _build_ui(self):
        style = ttk.Style()
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("Heading.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Hint.TLabel", foreground="gray")

        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(3, weight=1)

        ttk.Label(
            container,
            text="Analizador de procesos SECOP II (Datos Abiertos)",
            style="Heading.TLabel",
        ).grid(row=0, column=0, sticky="w")

        url_frame = ttk.LabelFrame(
            container, text="URL del detalle de proceso SECOP II", padding=10
        )
        url_frame.grid(row=1, column=0, sticky="ew", pady=(10, 6))
        url_frame.columnconfigure(0, weight=1)

        entry = ttk.Entry(url_frame, textvariable=self.url_var)
        entry.grid(row=0, column=0, sticky="ew")
        entry.focus_set()

        ttk.Button(url_frame, text="Analizar", command=self.on_analyze).grid(
            row=0, column=1, padx=(8, 0)
        )

        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=2, column=0, sticky="w", pady=(4, 8))
        ttk.Button(btn_frame, text="Descargar", command=self.on_save).pack(
            side="left", padx=4
        )
        ttk.Button(btn_frame, text="Limpiar", command=self.on_clear).pack(
            side="left", padx=4
        )

        frame_bottom = ttk.Frame(container, padding=10, relief="groove")
        frame_bottom.grid(row=3, column=0, sticky="nsew")
        frame_bottom.columnconfigure(0, weight=1)
        frame_bottom.rowconfigure(0, weight=1)

        self.text = tk.Text(
            frame_bottom,
            wrap="word",
            font=("Consolas", 10),
            background="#f8f9fa",
            relief="flat",
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        self.text.tag_configure("label", font=("Consolas", 10, "bold"))

        scroll = ttk.Scrollbar(frame_bottom, command=self.text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.text.config(yscrollcommand=scroll.set)

        help_text = (
            "Esta herramienta usa Datos Abiertos (p6dx-8zbt) de SECOP II.\n"
            "No depende de Selenium/Chrome y evita CAPTCHAs."
        )
        ttk.Label(container, text=help_text, style="Hint.TLabel").grid(
            row=4, column=0, sticky="w", pady=(6, 0)
        )

    def on_analyze(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning(
                "Falta URL", "Por favor pega una URL de detalle de proceso del SECOP II."
            )
            return

        self.text.delete("1.0", tk.END)

        try:
            record = fetch_from_open_data(url)
        except Exception as e:
            messagebox.showerror("Error al analizar", str(e))
            return
        self.last_record = record

        lines = []
        for field in FIELDS_ORDER:
            value = record.get(field, "No disponible")
            if field in ("Valor del contrato", "Presupuesto base"):
                value = self._format_currency(value)
            lines.append((field, value))
        lines.append(("Consultado", record.get("Consultado")))

        self._render(lines)

    def _render(self, items):
        """Renderiza pares etiqueta-valor con etiquetas en negrita."""
        self.text.delete("1.0", tk.END)
        for label, value in items:
            self.text.insert(tk.END, f"{label}: ", ("label",))
            self.text.insert(tk.END, f"{value}\n\n")

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
        """Guarda la última consulta en JSON."""
        if not self.last_record:
            messagebox.showwarning("Sin datos", "No hay resultados para descargar.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
            title="Guardar consulta"
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
        """Limpia la URL y el resultado mostrado."""
        self.url_var.set("")
        self.text.delete("1.0", tk.END)
        self.last_record = None


if __name__ == "__main__":
    app = SecopApp()
    app.mainloop()
