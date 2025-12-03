const form = document.getElementById("search-form");
const queryInput = document.getElementById("query");
const datasetSelect = document.getElementById("dataset");
const statusEl = document.getElementById("status");
const resultsGrid = document.getElementById("results-grid");
const resultsTitle = document.getElementById("results-title");
const datasetPill = document.getElementById("dataset-pill");
const limitWrapper = document.getElementById("limit-wrapper");
const toast = document.getElementById("toast");
const modal = document.getElementById("modal");
const modalBackdrop = document.getElementById("modal-backdrop");
const modalBody = document.getElementById("modal-body");
const modalTitle = document.getElementById("modal-title");
const modalClose = document.getElementById("modal-close");

const modeRadios = Array.from(document.querySelectorAll('input[name="mode"]'));

const DEFAULT_DATASETS = [
  "SECOP II - Procesos (p6dx-8zbt)",
  "SECOP II - Contratos electrónicos (jbjy-vk9h)",
];

document.addEventListener("DOMContentLoaded", () => {
  loadDatasets();
  setupModeToggle();
  form.addEventListener("submit", onSubmit);
  modalClose.addEventListener("click", closeModal);
  modalBackdrop.addEventListener("click", closeModal);
});

function setupModeToggle() {
  modeRadios.forEach((r) =>
    r.addEventListener("change", () => {
      const mode = getMode();
      limitWrapper.classList.toggle("hidden", mode !== "keyword");
      queryInput.placeholder =
        mode === "url"
          ? "https://community.secop.gov.co/..."
          : "policía, salud, tecnología...";
    })
  );
}

function getMode() {
  return modeRadios.find((r) => r.checked)?.value || "url";
}

async function loadDatasets() {
  try {
    const res = await fetch("/meta/datasets");
    if (!res.ok) throw new Error("No se pudo cargar datasets");
    const data = await res.json();
    const options = data.datasets?.map((d) => d.name) || DEFAULT_DATASETS;
    renderDatasetOptions(options, data.default);
  } catch (e) {
    renderDatasetOptions(DEFAULT_DATASETS, DEFAULT_DATASETS[0]);
    notify("No se pudieron cargar los datasets, usando valores por defecto.", "error");
  }
}

function renderDatasetOptions(options, defaultValue) {
  datasetSelect.innerHTML = "";
  options.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    datasetSelect.appendChild(opt);
  });
  if (defaultValue && options.includes(defaultValue)) {
    datasetSelect.value = defaultValue;
  }
}

async function onSubmit(e) {
  e.preventDefault();
  const query = queryInput.value.trim();
  if (!query) {
    notify("Ingresa una URL o palabra clave.", "error");
    return;
  }
  const dataset = datasetSelect.value;
  const mode = getMode();
  const limit = document.getElementById("limit").value || 20;

  setStatus("Consultando...");
  toggleForm(true);
  resultsGrid.innerHTML = "";
  resultsTitle.textContent = "Buscando...";

  try {
    if (mode === "url") {
      const res = await fetch("/lookup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: query, dataset }),
      });
      if (!res.ok) throw new Error(await extractError(res));
      const data = await res.json();
      renderRecords([data.record], dataset, `Resultado para URL/noticeUID (${dataset})`);
    } else {
      const params = new URLSearchParams({ term: query, dataset, limit });
      const res = await fetch(`/search?${params.toString()}`);
      if (!res.ok) throw new Error(await extractError(res));
      const data = await res.json();
      renderRecords(
        data.records || [],
        dataset,
        `Resultados (${data.count || 0}) en ${dataset}`
      );
    }
    notify("Consulta completada.", "success");
  } catch (err) {
    console.error(err);
    resultsTitle.textContent = "Error al consultar.";
    notify(err.message || "Error al consultar.", "error");
  } finally {
    setStatus("Listo.");
    toggleForm(false);
  }
}

async function extractError(res) {
  try {
    const data = await res.json();
    return data.detail || res.statusText;
  } catch (e) {
    return res.statusText;
  }
}

function renderRecords(records, dataset, title) {
  resultsGrid.innerHTML = "";
  datasetPill.textContent = dataset || "—";
  resultsTitle.textContent = title || "Sin resultados.";

  if (!records.length) {
    const empty = document.createElement("p");
    empty.className = "meta";
    empty.textContent = "No se encontraron resultados.";
    resultsGrid.appendChild(empty);
    return;
  }

  records.forEach((rec, idx) => {
    const card = document.createElement("div");
    card.className = "result-card";

    const titleEl = document.createElement("h3");
    titleEl.textContent = rec["Objeto / descripción"]?.slice(0, 120) || `Resultado #${idx + 1}`;
    card.appendChild(titleEl);

    const meta = document.createElement("p");
    meta.className = "meta";
    const entidad = rec["Entidad contratante"] || "—";
    const estado =
      rec["Estado del contrato"] || rec["Estado del procedimiento"] || rec["Adjudicado"] || "—";
    meta.textContent = `${entidad} • ${estado}`;
    card.appendChild(meta);

    const kv = document.createElement("div");
    kv.className = "kv";

    Object.entries(rec).forEach(([key, value]) => {
      kv.appendChild(renderKvLabel(key));
      kv.appendChild(renderKvValue(key, value));
    });

    card.appendChild(kv);

    if (rec["URL proceso"] && rec["URL proceso"] !== "No disponible") {
      const link = document.createElement("a");
      link.href = rec["URL proceso"];
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.className = "link-btn";
      link.textContent = "Abrir proceso en SECOP ↗";
      card.appendChild(link);
    }

    resultsGrid.appendChild(card);
  });
}

function formatValue(key, value) {
  if (value === null || value === undefined) return "No disponible";
  if (typeof value === "string" && value.trim() === "") return "No disponible";
  const str = String(value);
  const lower = key.toLowerCase();
  if (lower.includes("valor") || lower.includes("presupuesto")) {
    const num = Number(str.replace(/[^0-9.-]/g, ""));
    if (!Number.isNaN(num)) {
      return new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP",
        maximumFractionDigits: 0,
      }).format(num);
    }
  }
  return str;
}

function setStatus(text) {
  statusEl.textContent = text;
}

function toggleForm(disabled) {
  form.querySelectorAll("input, select, button").forEach((el) => {
    el.disabled = disabled;
  });
}

let toastTimer = null;
function notify(msg, type = "info") {
  toast.textContent = msg;
  toast.className = `toast ${type}`;
  toast.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 4000);
}

function renderKvLabel(text) {
  const label = document.createElement("div");
  label.className = "label";
  label.textContent = text;
  return label;
}

function renderKvValue(key, value) {
  const val = document.createElement("div");
  val.className = "value";
  const lower = key.toLowerCase();
  if (lower.includes("nit")) {
    const nit = String(value || "").replace(/\D/g, "");
    if (!nit) {
      val.textContent = "No disponible";
      return val;
    }
    const link = document.createElement("a");
    link.href = `https://www.rues.org.co/consultas?nit=${nit}`;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.className = "link-btn";
    link.textContent = value;
    val.appendChild(link);

    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Consultar proveedor";
    btn.style.marginTop = "4px";
    btn.style.padding = "8px 10px";
    btn.style.fontSize = "13px";
    btn.addEventListener("click", () => showProveedor(nit));
    val.appendChild(btn);
    return val;
  }

  val.textContent = formatValue(key, value);
  return val;
}

async function showProveedor(nit) {
  try {
    setStatus(`Consultando proveedor ${nit}...`);
    const res = await fetch(`/proveedor/${nit}`);
    if (!res.ok) throw new Error(await extractError(res));
    const data = await res.json();
    openModal(`Proveedor / NIT ${nit}`, data);
  } catch (e) {
    notify(e.message || "No se pudo consultar el proveedor.", "error");
  } finally {
    setStatus("Listo.");
  }
}

function openModal(title, obj) {
  modalTitle.textContent = title;
  modalBody.innerHTML = "";

  const kv = document.createElement("div");
  kv.className = "kv";
  Object.entries(obj || {}).forEach(([k, v]) => {
    kv.appendChild(renderKvLabel(k));
    const val = document.createElement("div");
    val.className = "value";
    val.textContent = v ?? "No disponible";
    kv.appendChild(val);
  });
  modalBody.appendChild(kv);

  modal.classList.remove("hidden");
  modalBackdrop.classList.remove("hidden");
}

function closeModal() {
  modal.classList.add("hidden");
  modalBackdrop.classList.add("hidden");
}
