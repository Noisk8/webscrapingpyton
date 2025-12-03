# Analizador SECOP (Datos Abiertos)

Proyecto con dos formas de uso:
- **API web (FastAPI)** lista para desplegar en Fly.io (`app/main.py`, `Dockerfile`, `fly.toml`).
- **App de escritorio Tkinter** (archivo original `analisis.py`, no se usa en Fly pero sigue en el repo).

## Ejecutar la API localmente
1) (Opcional) crea un entorno virtual: `python -m venv .venv` y actívalo.  
2) Instala dependencias: `pip install -r requirements.txt`  
3) Arranca la API: `uvicorn app.main:app --reload --port 8080`  
4) Prueba: `curl http://localhost:8080/health`

Endpoints principales:
- `POST /lookup` body `{"url": "...", "dataset": "SECOP II - Procesos (p6dx-8zbt)"}`  
- `GET /search?term=palabra&dataset=SECOP II - Procesos (p6dx-8zbt)`  
- `GET /proveedor/{nit}`  
- `GET /` muestra info básica.

## Despliegue en Fly.io
Hay dos caminos: usando la UI de Fly (como en tu captura) o la CLI. El archivo `fly.toml` ya está incluido y usa el puerto 8080.

### Con la CLI
1) Instala flyctl: `curl -L https://fly.io/install.sh | sh` (o binario para tu SO).  
2) Autentica: `flyctl auth login`  
3) Ajusta el nombre en `fly.toml` si quieres otro (`app = "webscrapingpyton"` por defecto).  
4) Despliega: `flyctl deploy --remote-only`

### Con la UI (screenshot)
- Deja `Current Working Directory` vacío (usa la raíz).  
- `Config path`: déjalo vacío (usa `fly.toml`).  
- App name: usa uno único en Fly (puedes quedarte con `webscrapingpyton` si está libre).  
- Da click en Deploy.

### GitHub Actions para Fly
- Workflow: `.github/workflows/deploy-fly.yml`
- Triggers: `push` a `main` o `workflow_dispatch`.
- Requiere el secreto `FLY_API_TOKEN` en el repo (lo obtienes con `flyctl auth token`).

## Despliegue de binarios (opcional, desktop)
- Workflow: `.github/workflows/build.yml`
- Triggers: `push` a `main`, tags `v*`, `workflow_dispatch`.
- Genera ejecutables PyInstaller para Linux y Windows y los sube como artifacts / release (si hay tag `v*`).

## Dependencias
- Python 3.11+
- API: `fastapi`, `uvicorn`, `requests`
- Desktop: Tkinter viene con Python en la mayoría de instalaciones.
