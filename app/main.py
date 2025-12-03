from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse
import re

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# --- Configuración de datasets ---

DATASETS: Dict[str, Dict[str, Any]] = {
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

PROVEEDORES_DATASET_ID = "qmzu-gj57"
DEFAULT_DATASET = list(DATASETS.keys())[0]


# --- Utilidades de normalización ---

def get_notice_uid(url: str) -> Optional[str]:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("noticeUID", "noticeUid", "noticeuid", "NoticeUID"):
        if params.get(key):
            return params[key][0]
    return None


def pick_first(row: dict, *keys) -> Optional[str]:
    for k in keys:
        val = row.get(k)
        if val not in (None, "", "NULL", "null"):
            return val
    return None


def format_plazo(row: dict) -> Optional[str]:
    duracion = row.get("duracion")
    unidad = row.get("unidad_de_duracion")
    if duracion and unidad:
        return f"{duracion} {unidad}"
    if duracion:
        return str(duracion)
    return None


def format_ubicacion(row: dict) -> Optional[str]:
    dep = row.get("departamento_entidad")
    ciudad = row.get("ciudad_entidad")
    parts = [p for p in [ciudad, dep] if p]
    return ", ".join(parts) if parts else None


def format_ubicacion_contrato(row: dict) -> Optional[str]:
    dep = row.get("departamento")
    ciudad = row.get("ciudad")
    parts = [p for p in [ciudad, dep] if p]
    return ", ".join(parts) if parts else None


def normalize_proceso(row: dict, notice_uid: str) -> dict:
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


# --- Consultas a Datos Abiertos ---

def fetch_from_open_data(url: str, dataset_key: str) -> dict:
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

    for k, v in record.items():
        if isinstance(v, str):
            record[k] = v.strip()
        if record[k] in ("", None):
            record[k] = "No disponible"
    record["Consultado"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return record


def fetch_by_keyword(term: str, dataset_key: str, limit: int = 25) -> List[dict]:
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


def fetch_proveedor_por_nit(nit: str) -> Optional[dict]:
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


# --- FastAPI app ---

app = FastAPI(title="Analizador SECOP API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/lookup")
def lookup(payload: Dict[str, Any]) -> dict:
    url = payload.get("url")
    dataset_key = payload.get("dataset", DEFAULT_DATASET)
    if not url:
        raise HTTPException(status_code=400, detail="Falta 'url'.")
    try:
        record = fetch_from_open_data(url, dataset_key)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except RuntimeError as re_err:
        raise HTTPException(status_code=404, detail=str(re_err)) from re_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"dataset": dataset_key, "record": record}


@app.get("/search")
def search(
    term: str = Query(..., min_length=1, description="Palabra clave a buscar"),
    dataset: str = Query(DEFAULT_DATASET, description="Dataset a usar"),
    limit: int = Query(25, ge=1, le=50, description="Cantidad máxima de resultados"),
) -> dict:
    try:
        records = fetch_by_keyword(term, dataset, limit)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"dataset": dataset, "count": len(records), "records": records}


@app.get("/proveedor/{nit}")
def proveedor(nit: str) -> dict:
    row = fetch_proveedor_por_nit(nit)
    if not row:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado.")
    return row


@app.get("/")
def root() -> dict:
    return {
        "message": "API Analizador SECOP (Datos Abiertos)",
        "endpoints": ["/lookup", "/search", "/proveedor/{nit}", "/health"],
    }
