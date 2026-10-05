/* global RehabLogic, askepFillDiagnoses, chrome */
"use strict";

const { Directory, validate, PERIOD_POST, OK, WARN, FAIL, INFO } = RehabLogic;
const N_SLOTS = 8;
const LEVEL_CLASS = { [OK]: "ok", [WARN]: "warn", [FAIL]: "fail", [INFO]: "info" };

const $ = (id) => document.getElementById(id);
let dir = null;
let mainListPeriod = null;
let fillArmed = false;
const state = { period: PERIOD_POST, st: false, main: "", comps: Array(N_SLOTS).fill(""), opts: {} };

// ------------------------------------------------------------------ збереження стану
// зберігаємо одразу: popup закривається, щойно користувач клацне поза ним
const save = () => chrome.storage.local.set({ askepRehab: state });

async function load() {
  const saved = (await chrome.storage.local.get("askepRehab")).askepRehab;
  if (saved) Object.assign(state, saved, { comps: [...(saved.comps || []), ...Array(N_SLOTS).fill("")].slice(0, N_SLOTS) });
  const data = await (await fetch(chrome.runtime.getURL("directory.json"))).json();
  dir = new Directory(data);
  $("source").textContent = `${dir.items.length} діагнозів · ${data.source}`;
  buildSlots();
  restoreInputs();
  refresh();
}

// ------------------------------------------------------------------ розмітка полів
function buildSlots() {
  const box = $("slots");
  for (let i = 0; i < N_SLOTS; i++) {
    const sec = document.createElement("section");
    sec.className = "field";
    sec.id = `slot-${i}`;
    sec.innerHTML = `
      <div class="field-head">
        <label for="comp-${i}">Супутній ${i + 1}${i === 0 ? '<span class="tag">з формулою</span>' : ""}</label>
        <span class="count" id="count-${i}"></span>
      </div>
      <div class="input-row">
        <input id="comp-${i}" list="dl-${i}" placeholder="Код або частина назви" autocomplete="off" spellcheck="false">
        <button class="clear" data-for="comp-${i}" title="Очистити" aria-label="Очистити супутній ${i + 1}">✕</button>
      </div>
      <datalist id="dl-${i}"></datalist>
      <div class="hint muted" id="hint-${i}" hidden></div>`;
    box.appendChild(sec);
  }
}

function restoreInputs() {
  document.querySelector(`input[name=period][value="${state.period}"]`).checked = true;
  $("st").checked = !!state.st;
  $("main").value = state.main;
  state.comps.forEach((v, i) => ($(`comp-${i}`).value = v));
  $("opt-label").value = state.opts.labelText || "Код діагнозу";
  $("opt-id").value = state.opts.inputId || "";
  $("opt-timeout").value = (state.opts.timeout || 6000) / 1000;
}

function fillDatalist(id, items) {
  const dl = $(id);
  const frag = document.createDocumentFragment();
  for (const d of items) {
    const o = document.createElement("option");
    o.value = d.name;
    frag.appendChild(o);
  }
  dl.replaceChildren(frag);
}

// ------------------------------------------------------------------ перерахунок
function refresh() {
  if (!dir) return;
  fillArmed = false;

  if (mainListPeriod !== state.period) {
    const mains = dir.mainCandidates(state.period);
    fillDatalist("dl-main", mains);
    $("main-count").textContent = `${mains.length} у списку`;
    mainListPeriod = state.period;
  }

  const main = dir.find(state.main);
  $("main").classList.toggle("unknown", !!state.main.trim() && !main);
  const selected = state.comps.map((c) => (c.trim() ? dir.find(c) : null));

  // показуємо заповнені поля + одне порожнє
  const last = state.comps.reduce((m, c, i) => (c.trim() ? i : m), -1);
  const shown = Math.min(N_SLOTS, Math.max(1, last + 2));
  for (let i = 0; i < N_SLOTS; i++) {
    $(`slot-${i}`).hidden = i >= shown;
    if (i >= shown) continue;
    const cand = main ? dir.companionCandidates(main, i, selected) : [];
    fillDatalist(`dl-${i}`, cand);
    $(`count-${i}`).textContent = main ? `${cand.length} у списку` : "";
    const unknown = !!state.comps[i].trim() && !selected[i];
    $(`comp-${i}`).classList.toggle("unknown", unknown);
    $(`hint-${i}`).hidden = !unknown;
    $(`hint-${i}`).textContent = unknown ? "Немає в довіднику — буде врахований як коморбідний стан" : "";
  }

  renderReport(validate(dir, state.period, state.main, state.comps, state.st));
  save();
}

function lineEl(l, cls = "") {
  const p = document.createElement("p");
  p.className = cls;
  const s = document.createElement("span");
  s.className = `l-${LEVEL_CLASS[l.level]}`;
  s.textContent = `${l.level} `;
  p.append(s, document.createTextNode(l.text));
  return p;
}

function renderReport(rep) {
  const sum = $("summary");
  const hasMain = !!dir.find(state.main);
  sum.hidden = !state.main.trim();
  sum.className = `summary ${LEVEL_CLASS[rep.summary.level]}`;
  sum.textContent = `${rep.summary.level}  ${rep.summary.text}`;

  const r = $("report");
  r.replaceChildren();
  const h = (t) => { const e = document.createElement("h3"); e.textContent = t; r.appendChild(e); };
  h("Основний діагноз");
  rep.main.forEach((l) => r.appendChild(lineEl(l)));
  if (rep.main_groups.length) { h("Формула основного"); rep.main_groups.forEach((l) => r.appendChild(lineEl(l))); }
  if (rep.companions.length) {
    h("Супутні");
    rep.companions.forEach(([name, ls], i) => {
      const t = document.createElement("p");
      t.className = "sub";
      t.textContent = `${i + 1}. ${name}`;
      r.appendChild(t);
      ls.forEach((l) => r.appendChild(lineEl(l, "in")));
    });
  }
  h("Несумісні поєднання");
  if (rep.exclusions.length) rep.exclusions.forEach((l) => r.appendChild(lineEl(l)));
  else r.appendChild(lineEl({ level: OK, text: "Не виявлено" }));

  const btn = $("fill");
  btn.disabled = !hasMain;
  btn.classList.remove("danger");
  btn.textContent = "Заповнити на сторінці";
  btn.dataset.level = rep.summary.level;
}

// ------------------------------------------------------------------ заповнення сторінки
function entries() {
  const list = [];
  const push = (text, role) => {
    const t = text.trim();
    if (!t) return;
    const d = dir.find(t);
    const code = d ? d.code : t.split(/\s+/)[0].toUpperCase();
    list.push({ role, code, name: d ? d.name : t });
  };
  push(state.main, "Основний");
  state.comps.forEach((c, i) => push(c, `Супутній ${i + 1}`));
  return list;
}

function fillOptions(extra = {}) {
  return {
    labelText: $("opt-label").value.trim() || "Код діагнозу",
    inputId: $("opt-id").value.trim(),
    timeout: Math.max(1, Number($("opt-timeout").value) || 6) * 1000,
    ...extra,
  };
}

async function runOnPage(args) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const [res] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: askepFillDiagnoses, args });
  return res.result;
}

function showResult(nodes) {
  $("fill-result").replaceChildren(...nodes);
}
const msg = (level, text) => lineEl({ level, text });

async function onFill() {
  const btn = $("fill");
  if (btn.dataset.level === FAIL && !fillArmed) {
    fillArmed = true;
    btn.classList.add("danger");
    btn.textContent = "Є помилки кодування — все одно заповнити?";
    return;
  }
  fillArmed = false;
  btn.disabled = true;
  btn.textContent = "Заповнюю…";
  showResult([msg(INFO, "Не перемикайте вкладку, поки триває заповнення.")]);
  try {
    const res = await runOnPage([entries(), fillOptions()]);
    if (!res.fields.length) {
      showResult([msg(FAIL, "На сторінці не знайдено полів «Код діагнозу». Відкрийте форму діагнозів або перевірте налаштування.")]);
    } else {
      showResult(res.results.map((r) => msg(r.level, `${r.role} ${r.code}: ${r.text}`)));
    }
  } catch (e) {
    showResult([msg(FAIL, `Не вдалося виконати на сторінці: ${e.message}`)]);
  } finally {
    refresh();
  }
}

async function onProbe() {
  try {
    const res = await runOnPage([[], fillOptions({ dryRun: true })]);
    if (!res.fields.length) {
      showResult([msg(FAIL, "Полів «Код діагнозу» не знайдено.")]);
      return;
    }
    showResult([
      msg(OK, `Знайдено полів: ${res.fields.length} (підсвічено на сторінці)`),
      ...res.fields.map((f) => msg(INFO, `Поле ${f.index}: ${f.value || "порожнє"}`)),
    ]);
  } catch (e) {
    showResult([msg(FAIL, `Не вдалося виконати на сторінці: ${e.message}`)]);
  }
}

// ------------------------------------------------------------------ події
document.addEventListener("input", (e) => {
  const t = e.target;
  if (t.name === "period") state.period = t.value;
  else if (t.id === "st") state.st = t.checked;
  else if (t.id === "main") state.main = t.value;
  else if (t.id.startsWith("comp-")) state.comps[Number(t.id.slice(5))] = t.value;
  else if (t.id.startsWith("opt-")) {
    Object.assign(state.opts, fillOptions());
    save();
    return;
  }
  else return;
  // повний перерахунок — коли значення впізнано, очищено або змінено період/перемикач
  const v = (t.value || "").trim();
  if (t.type === "radio" || t.type === "checkbox" || !v || dir.find(v)) refresh();
  else save();
});
document.addEventListener("change", (e) => { if (e.target.matches("#main, [id^=comp-]")) refresh(); });
document.addEventListener("click", (e) => {
  const id = e.target.dataset && e.target.dataset.for;
  if (!id) return;
  $(id).value = "";
  if (id === "main") state.main = "";
  else state.comps[Number(id.slice(5))] = "";
  refresh();
  $(id).focus();
});
$("fill").addEventListener("click", onFill);
$("probe").addEventListener("click", onProbe);
$("reset").addEventListener("click", () => {
  state.main = "";
  state.comps = Array(N_SLOTS).fill("");
  restoreInputs();
  showResult([]);
  refresh();
});

load().catch((e) => showResult([msg(FAIL, `Не вдалося завантажити довідник: ${e.message}`)]));
