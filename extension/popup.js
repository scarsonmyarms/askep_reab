/* global RehabLogic, chrome */
"use strict";

const { Directory, validate, planSlots, slotCandidates, slotFits, PERIOD_POST, OK, WARN, FAIL, INFO,
  SETTING_INPATIENT, SETTING_OUTPATIENT } = RehabLogic;
const LEVEL_CLASS = { [OK]: "ok", [WARN]: "warn", [FAIL]: "fail", [INFO]: "info" };
const ROLE_TAG = { main: "формула основного", pair: "пара †/*", comp1: "формула супутнього 1", free: "необов'язково" };

const $ = (id) => document.getElementById(id);
let dir = null;
let mainListPeriod = null;
let fillArmed = false;
let plan = [];
// values — значення полів супутніх за ключами плану (m0, m1, p:main, c0, f0 …)
const state = { setting: SETTING_INPATIENT, sr: false, period: PERIOD_POST, st: false, main: "", values: {}, conclusion: "", opts: {} };

// ------------------------------------------------------------------ збереження стану
// зберігаємо одразу: popup закривається, щойно користувач клацне поза ним
const save = () => chrome.storage.local.set({ askepRehab: state });

async function load() {
  const saved = (await chrome.storage.local.get("askepRehab")).askepRehab;
  if (saved) Object.assign(state, saved, { values: saved.values || {} });
  delete state.comps;                                   // старий формат (8 однакових полів)
  const data = await (await fetch(chrome.runtime.getURL("directory.json"))).json();
  dir = new Directory(data);
  const extra = (data.sources || []).length - 1;
  $("source").textContent = `${dir.items.length} діагнозів · ${data.source}${extra > 0 ? ` + ${extra} ${extra === 1 ? "файл" : extra < 5 ? "файли" : "файлів"} НСЗУ` : ""}`;
  $("source").title = (data.sources || [data.source]).join("\n");
  restoreInputs();
  refresh();
}

function restoreInputs() {
  document.querySelector(`input[name=period][value="${state.period}"]`).checked = true;
  document.querySelector(`input[name=setting][value="${state.setting}"]`).checked = true;
  $("sr").checked = !!state.sr;
  $("st").checked = !!state.st;
  $("main").value = state.main;
  $("conclusion").value = state.conclusion || "";
  $("conclusion-count").textContent = `${(state.conclusion || "").length} / 3000`;
  $("opt-label").value = state.opts.labelText || "Код діагнозу";
  $("opt-id").value = state.opts.inputId || "";
  $("opt-timeout").value = (state.opts.timeout || 6000) / 1000;
  $("opt-add").value = state.opts.addButtonText || "Додати ще один діагноз";
  $("opt-autoadd").checked = state.opts.autoAdd !== false;
  $("opt-type").value = state.opts.typeText || "Новий діагноз";
  $("opt-barthel").checked = state.opts.barthel !== false;
}

function fillDatalist(dl, items) {
  const frag = document.createDocumentFragment();
  for (const d of items) {
    const o = document.createElement("option");
    o.value = d.name;
    frag.appendChild(o);
  }
  dl.replaceChildren(frag);
}

// ------------------------------------------------------------------ поля супутніх (за ролями)
function slotSection(i) {
  const sec = document.createElement("section");
  const id = `slot-in-${i}`;
  sec.innerHTML = `
    <div class="field-head">
      <label for="${id}"><span class="num">Супутній ${i + 1}</span><span class="tag"></span></label>
      <span class="count"></span>
    </div>
    <div class="role-label muted"></div>
    <div class="input-row">
      <input id="${id}" list="dl-slot-${i}" placeholder="Код або частина назви" autocomplete="off" spellcheck="false">
      <button class="clear" title="Очистити" aria-label="Очистити супутній ${i + 1}">✕</button>
    </div>
    <datalist id="dl-slot-${i}"></datalist>
    <div class="hint" hidden></div>`;
  return sec;
}

// Поля перебудовуються лише тоді, коли змінився склад полів; інакше оновлюються на місці,
// щоб не збивати фокус і введення користувача.
function renderSlots(main) {
  const box = $("slots");
  const keys = plan.map((s) => s.key).join("|");
  if (box.dataset.keys !== keys) {
    const focusedKey = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.key : null;
    box.replaceChildren(...plan.map((_, i) => slotSection(i)));
    box.dataset.keys = keys;
    if (focusedKey) {
      const el = box.querySelector(`input[data-key="${CSS.escape(focusedKey)}"]`);
      if (el) setTimeout(() => el.focus(), 0);
    }
  }
  plan.forEach((s, i) => {
    const sec = box.children[i];
    sec.className = `field role-${s.role}`;
    sec.querySelector(".tag").textContent = ROLE_TAG[s.role];
    sec.querySelector(".role-label").textContent = s.role === "free" ? "" : s.label;
    const input = sec.querySelector("input");
    input.dataset.key = s.key;
    if (document.activeElement !== input && input.value !== s.value) input.value = s.value;
    sec.querySelector("button").dataset.key = s.key;
    const cand = slotCandidates(dir, main, plan, i);
    fillDatalist(sec.querySelector("datalist"), cand);
    sec.querySelector(".count").textContent = `${cand.length} у списку`;
    const hint = sec.querySelector(".hint");
    const v = (s.value || "").trim();
    let text = "", cls = "";
    if (v && s.diag && s.diag.source === "введено") { text = "Немає в довіднику — враховано лише за кодом"; cls = "muted"; }
    else if (v && !s.diag) { text = "Немає в довіднику — коморбідний стан"; cls = "muted"; }
    else if (slotFits(s) === false) { text = "⚠ Діагноз не відповідає ролі цього поля"; cls = "l-warn"; }
    input.classList.toggle("unknown", !!v && (!s.diag || s.diag.source === "введено"));
    hint.hidden = !text;
    hint.className = `hint ${cls}`;
    hint.textContent = text;
  });
}

// ------------------------------------------------------------------ перерахунок
function refresh() {
  if (!dir) return;
  fillArmed = false;

  if (mainListPeriod !== state.period) {
    const mains = dir.mainCandidates(state.period);
    fillDatalist($("dl-main"), mains);
    $("main-count").textContent = `${mains.length} у списку`;
    mainListPeriod = state.period;
  }

  const main = dir.find(state.main);
  $("main").classList.toggle("unknown", !!state.main.trim() && !main);
  plan = planSlots(dir, main, state.values);
  renderSlots(main);
  const out = state.setting === SETTING_OUTPATIENT;
  $("sr-wrap").hidden = !out;
  document.querySelector("header h1").textContent = out ? "Кодування · амбулаторія" : "Кодування діагнозів";
  renderReport(validate(dir, state.period, state.main, plan.map((s) => s.value), state.st,
    { setting: state.setting, sr: state.sr }));
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

  // амбулаторія: коротко — під підсумком, повністю — у деталях
  const sv = $("services");
  const head = rep.services.filter((l) => l.level !== INFO);
  sv.hidden = !head.length;
  sv.replaceChildren(...head.map((l) => {
    const e = document.createElement("span");
    e.className = `svc ${LEVEL_CLASS[l.level]}`;
    e.textContent = `${l.level} ${l.text.split(":")[0]}`;
    e.title = l.text;
    return e;
  }));
  if (head.length) sv.prepend(Object.assign(document.createElement("b"), { textContent: "Послуги за діагнозами: " }));

  const r = $("report");
  r.replaceChildren();
  const h = (t) => { const e = document.createElement("h3"); e.textContent = t; r.appendChild(e); };
  h("Основний діагноз");
  rep.main.forEach((l) => r.appendChild(lineEl(l)));
  if (rep.main_groups.length) { h("Формула основного"); rep.main_groups.forEach((l) => r.appendChild(lineEl(l))); }
  if (rep.companions.length) {
    h("Супутні");
    const nums = plan.map((s, i) => ((s.value || "").trim() ? i + 1 : 0)).filter(Boolean);
    rep.companions.forEach(([name, ls], i) => {
      const t = document.createElement("p");
      t.className = "sub";
      t.textContent = `Супутній ${nums[i] || i + 1}. ${name}`;
      r.appendChild(t);
      ls.forEach((l) => r.appendChild(lineEl(l, "in")));
    });
  }
  h("Несумісні поєднання");
  if (rep.exclusions.length) rep.exclusions.forEach((l) => r.appendChild(lineEl(l)));
  else r.appendChild(lineEl({ level: OK, text: "Не виявлено" }));
  if (rep.services.length) {
    h("Послуги амбулаторної реабілітації (за діагнозами)");
    rep.services.forEach((l) => r.appendChild(lineEl(l)));
  }

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
  plan.forEach((s, i) => push(s.value || "", `Супутній ${i + 1}`));
  return list;
}

function fillOptions(extra = {}) {
  return {
    labelText: $("opt-label").value.trim() || "Код діагнозу",
    inputId: $("opt-id").value.trim(),
    timeout: Math.max(1, Number($("opt-timeout").value) || 6) * 1000,
    addButtonText: $("opt-add").value.trim() || "Додати ще один діагноз",
    autoAdd: $("opt-autoadd").checked,
    typeText: $("opt-type").value.trim() || "Новий діагноз",
    barthel: $("opt-barthel").checked,
    conclusion: $("conclusion").value,
    ...extra,
  };
}

async function runOnPage(args) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const target = { tabId: tab.id };
  // 1) завантажуємо fill.js у сторінку; 2) викликаємо функцію вже там (вона живе в ізольованому світі розширення)
  await chrome.scripting.executeScript({ target, files: ["fill.js"] });
  const [res] = await chrome.scripting.executeScript({
    target,
    func: (entries, opts) => askepFillDiagnoses(entries, opts),
    args,
  });
  if (!res || res.result === undefined) throw new Error("сторінка не повернула результат (спробуйте оновити вкладку)");
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
      showResult(res.results.map((r) => msg(r.level, `${r.role}${r.code ? " " + r.code : ""}: ${r.text}`)));
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
  else if (t.name === "setting") state.setting = t.value;
  else if (t.id === "sr") state.sr = t.checked;
  else if (t.id === "st") state.st = t.checked;
  else if (t.id === "main") state.main = t.value;
  else if (t.id === "conclusion") {
    state.conclusion = t.value;
    $("conclusion-count").textContent = `${t.value.length} / 3000`;
    save();
    return;
  }
  else if (t.dataset && t.dataset.key) state.values[t.dataset.key] = t.value;
  else if (t.id && t.id.startsWith("opt-")) {
    Object.assign(state.opts, fillOptions());
    save();
    return;
  } else return;
  // повний перерахунок — коли значення впізнано, очищено або змінено період/перемикач
  const v = (t.value || "").trim();
  if (t.type === "radio" || t.type === "checkbox" || !v || dir.find(v)) refresh();
  else save();
});
document.addEventListener("change", (e) => {
  if (e.target.id === "main" || (e.target.dataset && e.target.dataset.key)) refresh();
});
document.addEventListener("click", (e) => {
  const b = e.target.closest("button.clear");
  if (!b) return;
  if (b.dataset.for === "main") {
    state.main = "";
    $("main").value = "";
    refresh();
    $("main").focus();
  } else if (b.dataset.key) {
    state.values[b.dataset.key] = "";
    refresh();
    const el = document.querySelector(`input[data-key="${CSS.escape(b.dataset.key)}"]`);
    if (el) el.focus();
  }
});
$("fill").addEventListener("click", onFill);
$("probe").addEventListener("click", onProbe);
$("reset").addEventListener("click", () => {
  state.main = "";
  state.values = {};
  state.conclusion = "";
  restoreInputs();
  showResult([]);
  refresh();
});

load().catch((e) => showResult([msg(FAIL, `Не вдалося завантажити довідник: ${e.message}`)]));
