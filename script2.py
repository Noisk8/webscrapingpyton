import tkinter as tk
from tkinter import ttk, messagebox
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import requests
import json
from tkinter import filedialog
import threading
import webbrowser
import re

# Configuración de datasets disponibles
# Puedes ampliar fácilmente agregando más fuentes de datos abiertos.
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


def format_ubicacion_contrato(row: dict) -> str | None:
    dep = row.get("departamento")
    ciudad = row.get("ciudad")
    parts = [p for p in [ciudad, dep] if p]
    return ", ".join(parts) if parts else None


def normalize_proceso(row: dict, notice_uid: str) -> dict:
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
        raise ValueError("No se encontró noticeUID en la URL.")

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


class SecopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Analizador SECOP II (Datos Abiertos)")
        self.geometry("900x700")
        self.url_var = tk.StringVar()
        self.dataset_var = tk.StringVar(value=list(DATASETS.keys())[0])
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
        container.rowconfigure(4, weight=1)

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

        # Selector de dataset
        ds_frame = ttk.Frame(container)
        ds_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(ds_frame, text="Fuente de datos:").pack(side="left", padx=(0, 6))
        ttk.Combobox(
            ds_frame,
            textvariable=self.dataset_var,
            values=list(DATASETS.keys()),
            state="readonly",
            width=45,
        ).pack(side="left", padx=(0, 8))

        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=3, column=0, sticky="w", pady=(0, 8))
        ttk.Button(btn_frame, text="Descargar", command=self.on_save).pack(
            side="left", padx=4
        )
        ttk.Button(btn_frame, text="Limpiar", command=self.on_clear).pack(
            side="left", padx=4
        )

        # Loader / estado
        status_frame = ttk.Frame(container)
        status_frame.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        status_frame.columnconfigure(1, weight=1)
        ttk.Label(status_frame, text="Estado:").grid(row=0, column=0, padx=(0, 6))
        self.status_label = ttk.Label(status_frame, text="Listo")
        self.status_label.grid(row=0, column=1, sticky="w")
        self.progress = ttk.Progressbar(status_frame, mode="indeterminate", length=180)
        self.progress.grid(row=0, column=2, padx=(10, 0))

        frame_bottom = ttk.Frame(container, padding=10, relief="groove")
        frame_bottom.grid(row=5, column=0, sticky="nsew")
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

        # Overlay de carga dentro del área de resultados
        self.loading_overlay = ttk.Label(
            frame_bottom,
            text="Cargando datos...",
            style="Heading.TLabel",
            anchor="center",
            background="#f8f9fa",
        )
        self.loading_overlay.place(relx=0.5, rely=0.5, anchor="center")
        self.loading_overlay.lower()  # oculto inicialmente

        scroll = ttk.Scrollbar(frame_bottom, command=self.text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.text.config(yscrollcommand=scroll.set)

        help_text = (
            "Esta herramienta usa Datos Abiertos de SECOP (p6dx-8zbt, jbjy-vk9h).\n"
            "No depende de Selenium/Chrome y evita CAPTCHAs."
        )
        ttk.Label(container, text=help_text, style="Hint.TLabel").grid(
            row=6, column=0, sticky="w", pady=(6, 0)
        )

    def on_analyze(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning(
                "Falta URL", "Por favor pega una URL de detalle de proceso del SECOP II."
            )
            return

        self.text.delete("1.0", tk.END)
        self.status_label.config(text="Consultando...")
        self._show_loader()
        self._set_controls_state("disabled")

        thread = threading.Thread(
            target=self._run_fetch,
            args=(url, self.dataset_var.get()),
            daemon=True,
        )
        thread.start()

    def _run_fetch(self, url, dataset_key):
        """Ejecuta la consulta en background y actualiza la UI al finalizar."""
        try:
            record = fetch_from_open_data(url, dataset_key)
            self.last_record = record

            fields = DATASETS[dataset_key]["fields"]
            currency_fields = DATASETS[dataset_key]["currency_fields"]
            lines = []
            for field in fields:
                value = record.get(field, "No disponible")
                if field in currency_fields:
                    value = self._format_currency(value)
                lines.append((field, value))
            lines.append(("Consultado", record.get("Consultado")))

            self.after(0, lambda: self._render(lines))
            self.after(0, lambda: self.status_label.config(text="Listo"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error al analizar", str(e)))
            self.after(0, lambda: self.status_label.config(text="Error"))
        finally:
            self.after(0, self._hide_loader)
            self.after(0, lambda: self._set_controls_state("normal"))

    def _render(self, items):
        """Renderiza pares etiqueta-valor con etiquetas en negrita."""
        self.text.delete("1.0", tk.END)
        nit_labels = {"NIT entidad", "NIT proveedor"}
        self.link_targets = {}
        for idx, (label, value) in enumerate(items):
            self.text.insert(tk.END, f"{label}: ", ("label",))
            if label in nit_labels and value not in ("No disponible", None):
                nit_clean = re.sub(r"\D", "", str(value))
                url = self._build_nit_url(nit_clean) if nit_clean else None
                self._insert_link(idx, value, url)
                self.text.insert(tk.END, "\n\n")
            else:
                self.text.insert(tk.END, f"{value}\n\n")
        self.text.see("1.0")
        self._hide_loader()

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
        self.status_label.config(text="Listo")
        self._hide_loader()
        self._set_controls_state("normal")

    def _set_controls_state(self, state):
        """Habilita o deshabilita controles mientras carga."""
        for child in self.winfo_children():
            self._toggle_state_recursive(child, state)

    def _toggle_state_recursive(self, widget, state):
        if isinstance(widget, (ttk.Button, ttk.Entry, ttk.Combobox)):
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
        """Muestra el loader y el texto de carga."""
        self.progress.start(10)
        self.loading_overlay.lift()

    def _hide_loader(self):
        """Oculta el loader y detiene la barra de progreso."""
        self.progress.stop()
        self.loading_overlay.lower()

    def _build_nit_url(self, nit: str) -> str:
        """Genera un enlace para consultar NIT en directorios públicos."""
        # RUES es confiable para NIT en Colombia
        return f"https://www.rues.org.co/consultas?nit={nit}"

    def _insert_link(self, idx: int, value: str, url: str | None):
        """Inserta texto como enlace clicable en el Text."""
        start_index = self.text.index(tk.END)
        self.text.insert(tk.END, f"{value}")
        end_index = self.text.index(tk.END)
        if not url:
            return
        tag_name = f"link-{idx}"
        self.text.tag_add(tag_name, start_index, end_index)
        self.text.tag_config(
            tag_name,
            foreground="blue",
            underline=1,
        )
        # Bind directo al tag para que siempre responda
        self.text.tag_bind(tag_name, "<Button-1>", lambda e, link=url: webbrowser.open_new_tab(link))
        self.text.tag_bind(tag_name, "<Enter>", lambda e: self.text.config(cursor="hand2"))
        self.text.tag_bind(tag_name, "<Leave>", lambda e: self.text.config(cursor=""))

if __name__ == "__main__":
    app = SecopApp()
    app.mainloop()
