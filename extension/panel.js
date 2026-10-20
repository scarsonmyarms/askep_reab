/*
 * Панель «Кодування» на сторінці Askep (у стилі «Askep Помічник»).
 * Ізольована в Shadow DOM, щоб стилі Askep (Bootstrap, Vuetify) і панелі не впливали одне на одне.
 * Дані вставляються тільки як текст (textContent), HTML-розмітка з рядків не будується.
 * Залежності (вставляються разом): directory.js (REHAB_DIRECTORY), logic.js (RehabLogic), fill.js (askepFillDiagnoses).
 */
(function () {
  "use strict";
  if (globalThis.__askepCoding) { globalThis.__askepCoding.open(); return; }

  const L = globalThis.RehabLogic;
  const DATA = globalThis.REHAB_DIRECTORY;
  const fillPage = globalThis.askepFillDiagnoses;
  const { OK, WARN, FAIL, INFO, PERIOD_POST, PERIOD_LONG, SETTING_INPATIENT, SETTING_OUTPATIENT } = L;
  const ext = typeof browser !== "undefined" ? browser : (typeof chrome !== "undefined" ? chrome : null);

  // збереження стану між відкриттями (як і раніше — ключ askepRehab)
  const storage = {
    async get() { try { return (await ext.storage.local.get("askepRehab")).askepRehab || null; } catch (_) { return null; } },
    set(v) { try { ext.storage.local.set({ askepRehab: v }); } catch (_) { /* без сховища — лише на час сторінки */ } },
  };

  const STYLE = `
    :host { all: initial; }
    * { box-sizing: border-box; }
    .wrap {
      --ink: #1C2B36; --muted: #5B6B77; --paper: #FFFFFF; --mist: #F3F6F8;
      --line: #DCE3E8; --field: #B9C5CE; --accent: #0F6E8C; --accent-soft: #EEF6F9;
      --active: #1F7A4D; --stopped: #A63A2E; --pending: #9A6200; --neutral: #7A8A96;
      font: 14px/1.45 "Segoe UI", system-ui, -apple-system, sans-serif; color: var(--ink);
    }
    button, input, textarea { font: inherit; color: inherit; }
    button { cursor: pointer; }
    button:focus-visible, input:focus-visible, textarea:focus-visible, h2:focus-visible, summary:focus-visible {
      outline: 2px solid var(--accent); outline-offset: 2px;
    }
    [hidden] { display: none !important; }
    .launcher {
      position: fixed; right: 20px; bottom: 20px; z-index: 2147483000;
      display: flex; align-items: center; gap: 8px; padding: 9px 14px;
      border: 1px solid var(--accent); border-radius: 999px; background: var(--paper); color: var(--accent);
      font-weight: 600; box-shadow: 0 2px 10px rgba(15, 110, 140, .18);
    }
    .launcher:hover { background: var(--accent-soft); }
    .sheet {
      position: fixed; top: 0; right: 0; bottom: 0; z-index: 2147483001;
      width: min(420px, 100vw); display: flex; flex-direction: column;
      background: var(--mist); border-left: 1px solid var(--line); box-shadow: -8px 0 24px rgba(28, 43, 54, .12);
    }
    @media (prefers-reduced-motion: no-preference) {
      .sheet { animation: slide .18s ease-out; }
      @keyframes slide { from { transform: translateX(24px); opacity: 0; } to { transform: none; opacity: 1; } }
    }
    header { background: var(--paper); border-bottom: 1px solid var(--line); }
    .titlebar { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px 6px; }
    h2 { margin: 0; font-size: 16px; font-weight: 600; }
    .tabs { display: flex; gap: 4px; padding: 0 12px; }
    .tab { height: 44px; padding: 0 8px; border: 0; border-bottom: 2px solid var(--accent); background: none;
      color: var(--accent); font-weight: 600; white-space: nowrap; cursor: default; }
    .ghost { padding: 4px 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--paper); font-size: 13px; }
    .ghost:hover { border-color: var(--accent); color: var(--accent); }
    .icon { width: 32px; height: 32px; padding: 0; text-align: center; }
    .primary { height: 48px; border: 0; border-radius: 6px; background: var(--accent); color: #fff; font-size: 15px; font-weight: 600; padding: 0 18px; }
    .primary:hover { background: #0B5E78; }
    .primary[disabled] { opacity: .55; cursor: default; }
    .secondary { height: 46px; padding: 0 16px; border: 1px solid var(--field); border-radius: 6px; background: var(--paper); font-size: 14px; }
    .outline { height: 40px; padding: 0 14px; border: 1px solid var(--accent); border-radius: 6px; background: var(--paper); color: var(--accent); font-weight: 600; }
    .plain { height: 40px; padding: 0 14px; border: 1px solid var(--field); border-radius: 6px; background: var(--paper); }
    .bar { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 18px;
      background: var(--paper); border-bottom: 1px solid var(--line); flex-wrap: wrap; }
    .seg { display: flex; border: 1px solid var(--field); border-radius: 6px; overflow: hidden; }
    .seg button { height: 32px; padding: 0 8px; border: 0; background: var(--paper); font-size: 13px; }
    .seg button[aria-pressed="true"] { background: var(--accent); color: #fff; font-weight: 600; }
    .seg.soft button[aria-pressed="true"] { background: var(--accent-soft); color: var(--accent); }
    .body { flex: 1; overflow-y: auto; }
    .pad { padding: 16px 18px; display: flex; flex-direction: column; gap: 14px; }
    footer { padding: 10px 18px; font-size: 12px; color: var(--muted); border-top: 1px solid var(--line); background: var(--paper); }
    .field { display: flex; flex-direction: column; gap: 6px; }
    .field > label { font-weight: 600; }
    .in { height: 44px; padding: 0 12px; border: 1px solid var(--field); border-radius: 6px; font-size: 15px; background: var(--paper); width: 100%; min-width: 0; }
    .in.warn { border-color: #E8D3A8; }
    .row-in { display: flex; gap: 6px; }
    .hint { margin: 0; color: var(--muted); font-size: 13px; }
    .hint.warn { color: var(--pending); }
    .checks { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--muted); }
    .checks label, label.check { display: flex; gap: 8px; align-items: flex-start; }
    label.check { font-size: 13px; color: var(--ink); }
    ol.slots { list-style: none; margin: 0; padding: 0; background: var(--paper); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
    ol.slots li { position: relative; padding: 12px 16px 12px 20px; border-bottom: 1px solid var(--line); display: flex; flex-direction: column; gap: 6px; }
    ol.slots li:last-child { border-bottom: 0; }
    ol.slots li::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--neutral); }
    ol.slots li[data-tone="active"]::before { background: var(--active); }
    ol.slots li[data-tone="stopped"]::before { background: var(--stopped); }
    ol.slots li[data-tone="pending"]::before { background: var(--pending); }
    .slot-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
    .slot-head label { font-weight: 600; white-space: nowrap; }
    .role { font-size: 13px; font-weight: 600; text-align: right; color: var(--muted); overflow-wrap: anywhere; }
    li[data-tone="active"] .role { color: var(--active); }
    li[data-tone="stopped"] .role { color: var(--stopped); }
    li[data-tone="pending"] .role { color: var(--pending); }
    .sin { height: 40px; padding: 0 10px; border: 1px solid var(--field); border-radius: 6px; background: var(--paper); width: 100%; min-width: 0; }
    .count { color: var(--muted); font-size: 12px; }
    .card { background: var(--paper); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; }
    .problem { background: var(--paper); border: 1px solid #E5C3BE; border-radius: 8px; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; }
    .problem.warn { border-color: #E8D3A8; }
    .problem.info { border-color: var(--line); }
    .problem h3 { margin: 0; font-size: 15px; font-weight: 600; color: var(--stopped); }
    .problem.warn h3 { color: #7A4E00; }
    .problem.info h3 { color: var(--ink); }
    .problem p { margin: 0; font-size: 13px; }
    .problem ul { margin: 0; padding-left: 18px; font-size: 13px; }
    .actions { display: flex; gap: 8px; margin-top: 4px; flex-wrap: wrap; }
    .actions .primary { flex: 1; height: 46px; }
    .ok-card { background: var(--paper); border: 1px solid #BFDCCB; border-radius: 8px; padding: 12px 14px; display: flex; gap: 10px; align-items: center; color: var(--active); font-weight: 600; }
    .badge { flex: none; width: 28px; height: 28px; border-radius: 50%; background: var(--active); display: flex; align-items: center; justify-content: center; }
    .warnbar { background: #FFF4DE; border: 1px solid #F0DDB5; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #6B4500; font-weight: 600; }
    .chips { display: flex; flex-wrap: wrap; gap: 4px 6px; align-items: center; font-size: 12px; }
    .chip { padding: 1px 8px; border-radius: 999px; border: 1px solid var(--line); background: var(--paper); }
    .chip.ok { color: var(--active); border-color: #BFDCCB; } .chip.warn { color: var(--pending); border-color: #E8D3A8; } .chip.fail { color: var(--stopped); border-color: #E5C3BE; }
    details > summary { cursor: pointer; color: var(--accent); font-size: 13px; }
    .report { font-size: 13px; padding-top: 6px; }
    .report h4 { margin: 8px 0 2px; font-size: 13px; }
    .report p { margin: 1px 0 1px 8px; }
    .l-ok { color: var(--active); } .l-warn { color: var(--pending); } .l-fail { color: var(--stopped); } .l-info { color: var(--accent); }
    textarea.in { height: auto; min-height: 76px; padding: 8px 10px; font-size: 14px; resize: vertical; }
    .tools { display: flex; gap: 6px; flex-wrap: wrap; }
    .settings { display: grid; gap: 6px; padding-top: 6px; font-size: 12px; color: var(--muted); }
    .settings label { display: grid; grid-template-columns: 170px minmax(0, 1fr); align-items: center; gap: 6px; }
    .settings input[type="text"], .settings input[type="number"] { height: 30px; padding: 0 8px; border: 1px solid var(--field); border-radius: 6px; }
    .confirm { background: var(--paper); border: 2px solid var(--accent); border-radius: 10px; padding: 18px;
      display: flex; flex-direction: column; gap: 12px; box-shadow: 0 6px 18px rgba(15, 110, 140, .14); }
    .confirm h3 { margin: 0; font-size: 17px; font-weight: 600; }
    .confirm p { margin: 0; font-size: 13px; }
    .who { margin: 0; padding: 10px 12px; background: var(--mist); border-radius: 6px; display: grid; grid-template-columns: 92px minmax(0, 1fr); gap: 6px 10px; font-size: 13px; }
    .who dt { color: var(--muted); } .who dd { margin: 0; overflow-wrap: anywhere; }
    ol.steps { margin: 0; padding: 0; list-style: none; background: var(--paper); border: 1px solid var(--line); border-radius: 8px; }
    ol.steps li { display: flex; gap: 12px; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--line); }
    ol.steps li:last-child { border-bottom: 0; }
    ol.steps li[data-state="active"] { background: var(--accent-soft); font-weight: 600; }
    .dot { flex: none; width: 26px; height: 26px; border-radius: 50%; border: 2px solid #C7D1D9; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 13px; font-weight: 700; }
    [data-state="done"] .dot { background: var(--active); border-color: var(--active); }
    [data-state="warn"] .dot { background: var(--pending); border-color: var(--pending); }
    [data-state="fail"] .dot { background: var(--stopped); border-color: var(--stopped); }
    [data-state="active"] .dot { border: 3px solid var(--accent); border-right-color: #BFDCE6; }
    @media (prefers-reduced-motion: no-preference) {
      [data-state="active"] .dot { animation: spin .9s linear infinite; }
      @keyframes spin { to { transform: rotate(360deg); } }
    }
    .steps .label { flex: 1; min-width: 0; }
    .steps .note { flex: none; max-width: 52%; font-size: 12px; font-weight: 400; color: var(--muted); text-align: right; }
    [data-state="warn"] .note { color: var(--pending); } [data-state="fail"] .note { color: var(--stopped); }
    h3.view { margin: 0; font-size: 17px; font-weight: 600; }
  `;

  const SVG_NS = "http://www.w3.org/2000/svg";
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : String(v));
    }
    for (const c of children.flat()) {
      if (c === null || c === undefined || c === false) continue;
      el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }
  function tick() {
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("width", "14"); svg.setAttribute("height", "14"); svg.setAttribute("viewBox", "0 0 16 16"); svg.setAttribute("aria-hidden", "true");
    const p = document.createElementNS(SVG_NS, "path");
    p.setAttribute("d", "M3 8.5l3 3 7-7"); p.setAttribute("fill", "none"); p.setAttribute("stroke", "#FFFFFF");
    p.setAttribute("stroke-width", "2.2"); p.setAttribute("stroke-linecap", "round"); p.setAttribute("stroke-linejoin", "round");
    svg.append(p);
    return svg;
  }
  const LEVEL_CLASS = { [OK]: "ok", [WARN]: "warn", [FAIL]: "fail", [INFO]: "info" };
  const plural = (n, one, few, many) => (n % 10 === 1 && n % 100 !== 11 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many);

  // ------------------------------------------------------------------ стан
  const dir = new L.Directory(DATA);
  const state = {
    setting: SETTING_INPATIENT, sr: false, period: PERIOD_POST, st: false, main: "", values: {}, conclusion: "",
    opts: {}, dismissed: [],
  };
  let view = "form";         // form | confirm | run
  let plan = [];
  let report = null;
  let mainListPeriod = null;
  let run = { steps: [], running: false, fieldsFound: true, error: null };
  const save = () => storage.set(state);

  // ------------------------------------------------------------------ оболонка
  const host = h("div", { id: "askep-coding-root" });
  const shadow = host.attachShadow({ mode: "open" });
  const wrap = h("div", { class: "wrap" });
  const launcher = h("button", { class: "launcher", type: "button", "aria-expanded": "false", onclick: () => toggle() }, "Кодування");
  const titleEl = h("h2", { tabindex: "-1" }, "Askep Помічник");
  const closeBtn = h("button", { class: "ghost icon", type: "button", "aria-label": "Закрити панель", title: "Закрити", onclick: () => close() }, "✕");
  const segSetting = h("div", { class: "seg", role: "group", "aria-label": "Умови надання" });
  const segPeriod = h("div", { class: "seg soft", role: "group", "aria-label": "Реабілітаційний період" });
  const bodyEl = h("div", { class: "body", role: "tabpanel", "aria-live": "polite" });
  const footerEl = h("footer");
  const sheet = h("aside", { class: "sheet", hidden: true, role: "dialog", "aria-label": "Кодування діагнозів" },
    h("header", null,
      h("div", { class: "titlebar" }, titleEl, closeBtn),
      h("nav", { class: "tabs", role: "tablist", "aria-label": "Розділи помічника" },
        h("button", { class: "tab", type: "button", role: "tab", "aria-selected": "true" }, "Кодування"))),
    h("div", { class: "bar" }, segSetting, segPeriod),
    bodyEl, footerEl);
  sheet.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  wrap.append(launcher, sheet);
  shadow.append(h("style", { text: STYLE }), wrap);

  function segButtons(box, options, current, onPick) {
    box.replaceChildren(...options.map((o) =>
      h("button", { type: "button", "aria-pressed": String(o === current), onclick: () => onPick(o) }, o)));
  }

  // ------------------------------------------------------------------ форма (будується один раз, оновлюється на місці)
  const dlMain = h("datalist", { id: "ac-dl-main" });
  const mainInput = h("input", { class: "in", id: "ac-main", list: "ac-dl-main", placeholder: "Код або частина назви", autocomplete: "off", spellcheck: "false" });
  const mainClear = h("button", { class: "ghost icon", type: "button", "aria-label": "Очистити основний діагноз", title: "Очистити" }, "✕");
  const mainHint = h("p", { class: "hint" });
  const stBox = h("input", { type: "checkbox", id: "ac-st" });
  const srBox = h("input", { type: "checkbox", id: "ac-sr" });
  const srWrap = h("label", null, srBox, "Є запис СР1/СР2/СР3 за останні 3 місяці (послуга АР1)");
  const slotsBox = h("ol", { class: "slots", "aria-label": "Супутні діагнози" });
  const adviceBox = h("div", { class: "pad", style: "padding: 0" });
  const statusBox = h("div");
  const servicesBox = h("div", { class: "chips" });
  const reportBox = h("div", { class: "report" });
  const conclusion = h("textarea", { class: "in", id: "ac-concl", rows: "3", maxlength: "3000",
    placeholder: "Текст для поля «Заключення лікаря» на вкладці «Діагностичні звіти»" });
  const conclCount = h("p", { class: "hint" }, "0 / 3000");
  const barthelBox = h("input", { type: "checkbox", id: "ac-barthel" });
  const fillBtn = h("button", { class: "primary", type: "button" }, "Заповнити на сторінці");
  const probeBtn = h("button", { class: "ghost", type: "button" }, "Знайти поля на сторінці");
  const resetBtn = h("button", { class: "ghost", type: "button" }, "Очистити все");
  const probeOut = h("div", { class: "report" });
  const opt = {
    labelText: h("input", { type: "text", value: "Код діагнозу" }),
    inputId: h("input", { type: "text", placeholder: "напр. input-297" }),
    timeout: h("input", { type: "number", min: "1", max: "30", value: "6" }),
    addButtonText: h("input", { type: "text", value: "Додати ще один діагноз" }),
    typeText: h("input", { type: "text", value: "Новий діагноз" }),
    autoAdd: h("input", { type: "checkbox", checked: true }),
  };
  const formView = h("div", { class: "pad" },
    h("div", { class: "field" },
      h("label", { for: "ac-main" }, "Основний діагноз"),
      h("div", { class: "row-in" }, mainInput, mainClear), dlMain, mainHint),
    h("div", { class: "checks" },
      h("label", null, stBox, "Коди S/T у формулах T90–T95 обов'язкові"), srWrap),
    slotsBox, adviceBox, statusBox, servicesBox,
    h("details", null, h("summary", null, "Деталі перевірки"), reportBox),
    h("div", { class: "field" }, h("label", { for: "ac-concl" }, "Заключення лікаря"), conclusion, conclCount),
    h("label", { class: "check" }, barthelBox, "Додати звіт 96037-00 і спостереження Barthel_Extended (шкала Бартел)"),
    fillBtn,
    h("div", { class: "tools" }, probeBtn, resetBtn), probeOut,
    h("details", null, h("summary", null, "Налаштування заповнення"),
      h("div", { class: "settings" },
        h("label", null, "Підпис поля коду", opt.labelText),
        h("label", null, "id поля (необов'язково)", opt.inputId),
        h("label", null, "Очікування списку, с", opt.timeout),
        h("label", null, "Текст кнопки додавання", opt.addButtonText),
        h("label", null, "Тип діагнозу для нових блоків", opt.typeText),
        h("label", null, "Додавати блоки автоматично", opt.autoAdd))));

  function fillDatalist(dl, items) {
    const frag = document.createDocumentFragment();
    for (const d of items) frag.append(h("option", { value: d.name }));
    dl.replaceChildren(frag);
  }

  function slotRow(i) {
    const id = `ac-slot-${i}`;
    return h("li", null,
      h("div", { class: "slot-head" }, h("label", { for: id }, `Супутній ${i + 1}`), h("span", { class: "role" })),
      h("div", { class: "row-in" },
        h("input", { class: "sin", id, list: `ac-dl-${i}`, placeholder: "Код або частина назви", autocomplete: "off", spellcheck: "false" }),
        h("button", { class: "ghost icon", type: "button", "aria-label": `Очистити супутній ${i + 1}`, title: "Очистити", "data-clear": "1" }, "✕")),
      h("datalist", { id: `ac-dl-${i}` }),
      h("p", { class: "hint", hidden: true }),
      h("span", { class: "count" }));
  }

  function roleText(s) {
    if (s.role === "free") return "необов'язково";
    if (s.role === "pair") return s.label;
    const i = s.label.indexOf(": ");
    return i >= 0 ? s.label.slice(i + 2) : s.label;
  }

  function renderSlots(main) {
    const keys = plan.map((s) => s.key).join("|");
    if (slotsBox.dataset.keys !== keys) {
      const focused = shadow.activeElement && shadow.activeElement.dataset ? shadow.activeElement.dataset.key : null;
      slotsBox.replaceChildren(...plan.map((_, i) => slotRow(i)));
      slotsBox.dataset.keys = keys;
      if (focused) {
        const el = slotsBox.querySelector(`input[data-key="${CSS.escape(focused)}"]`);
        if (el) setTimeout(() => el.focus(), 0);
      }
    }
    slotsBox.hidden = !plan.length;
    plan.forEach((s, i) => {
      const li = slotsBox.children[i];
      const input = li.querySelector("input");
      input.dataset.key = s.key;
      li.querySelector("[data-clear]").dataset.key = s.key;
      if (shadow.activeElement !== input && input.value !== s.value) input.value = s.value;
      const cand = L.slotCandidates(dir, main, plan, i);
      fillDatalist(li.querySelector("datalist"), cand);
      li.querySelector(".count").textContent = `${cand.length} у списку`;
      const v = (s.value || "").trim();
      const fits = L.slotFits(s);
      let tone = "neutral", hint = "";
      if (!v) tone = s.role === "free" ? "neutral" : "stopped";
      else if (!s.diag) { tone = "pending"; hint = "Немає в довіднику — коморбідний стан"; }
      else if (s.diag.source === "введено") { tone = "pending"; hint = "Немає в довіднику — враховано лише за кодом"; }
      else if (fits === false) { tone = "pending"; hint = "Діагноз не відповідає ролі цього поля"; }
      else tone = "active";
      li.dataset.tone = tone;
      li.querySelector(".role").textContent = roleText(s);
      const hp = li.querySelector(".hint");
      hp.hidden = !hint;
      hp.className = `hint${tone === "pending" ? " warn" : ""}`;
      hp.textContent = hint;
    });
  }

  const allProblemLines = (rep, level) => {
    const out = [];
    const adviceText = new Set(rep.advice.map((a) => `${a.title}: ${a.text}`));
    for (const l of [...rep.main, ...rep.main_groups, ...rep.exclusions]) if (l.level === level && !adviceText.has(l.text)) out.push(l.text);
    const nums = plan.map((s, i) => ((s.value || "").trim() ? i + 1 : 0)).filter(Boolean);
    rep.companions.forEach(([, ls], i) => ls.forEach((l) => { if (l.level === level) out.push(`Супутній ${nums[i] || i + 1}: ${l.text}`); }));
    return out;
  };

  function renderStatus(rep) {
    statusBox.replaceChildren();
    if (!dir.find(state.main)) return;
    const lvl = rep.summary.level;
    if (lvl === OK) {
      statusBox.append(h("div", { class: "ok-card" }, h("div", { class: "badge" }, tick()), rep.summary.text));
      return;
    }
    if (lvl === FAIL) {
      const lines = allProblemLines(rep, FAIL);
      statusBox.append(h("div", { class: "problem" }, h("h3", null, rep.summary.text),
        h("ul", null, lines.slice(0, 6).map((t) => h("li", null, t))),
        lines.length > 6 ? h("p", null, `і ще ${lines.length - 6} — див. «Деталі перевірки»`) : null));
      return;
    }
    const lines = allProblemLines(rep, WARN);
    statusBox.append(h("div", { class: "warnbar" }, `${WARN} ${rep.summary.text}`),
      lines.length ? h("div", { class: "problem warn", style: "margin-top: 8px" },
        h("ul", null, lines.slice(0, 6).map((t) => h("li", null, t)))) : null);
  }

  function renderAdvice(rep, main) {
    adviceBox.replaceChildren();
    for (const a of rep.advice) {
      const key = `${main.code}|${a.kind}|${a.swap_code || ""}`;
      if (state.dismissed.includes(key)) continue;
      const cls = a.level === INFO ? "problem info" : "problem warn";
      adviceBox.append(h("div", { class: cls },
        h("h3", null, a.title), h("p", null, a.text),
        h("div", { class: "actions" },
          a.swap ? h("button", { class: "outline", type: "button", onclick: () => swap(a.swap) }, `Зробити ${a.swap_code} основним`) : null,
          h("button", { class: "plain", type: "button", onclick: () => { state.dismissed.push(key); refresh(); } }, "Залишити"))));
    }
  }

  function renderServices(rep) {
    const head = rep.services.filter((l) => l.level !== INFO);
    servicesBox.replaceChildren();
    if (!head.length) return;
    servicesBox.append(h("b", null, "Послуги за діагнозами:"),
      ...head.map((l) => h("span", { class: `chip ${LEVEL_CLASS[l.level]}`, title: l.text }, `${l.level} ${l.text.split(":")[0]}`)));
  }

  function renderReport(rep) {
    const line = (l) => h("p", null, h("span", { class: `l-${LEVEL_CLASS[l.level]}` }, `${l.level} `), l.text);
    const nums = plan.map((s, i) => ((s.value || "").trim() ? i + 1 : 0)).filter(Boolean);
    reportBox.replaceChildren(
      h("h4", null, "Основний діагноз"), ...rep.main.map(line),
      rep.main_groups.length ? h("h4", null, "Формула основного") : null, ...rep.main_groups.map(line),
      ...rep.companions.flatMap(([name, ls], i) => [h("h4", null, `Супутній ${nums[i] || i + 1}. ${name}`), ...ls.map(line)]),
      h("h4", null, "Несумісні поєднання"),
      ...(rep.exclusions.length ? rep.exclusions.map(line) : [line({ level: OK, text: "Не виявлено" })]),
      rep.services.length ? h("h4", null, "Послуги амбулаторної реабілітації (за діагнозами)") : null,
      ...rep.services.map(line));
  }

  function refresh() {
    segButtons(segSetting, [SETTING_INPATIENT, SETTING_OUTPATIENT], state.setting, (v) => { state.setting = v; refresh(); });
    segButtons(segPeriod, [PERIOD_POST, PERIOD_LONG], state.period, (v) => { state.period = v; refresh(); });
    if (view !== "form") { save(); return; }
    if (mainListPeriod !== state.period) {
      fillDatalist(dlMain, dir.mainCandidates(state.period));
      mainListPeriod = state.period;
    }
    const main = dir.find(state.main);
    if (shadow.activeElement !== mainInput && mainInput.value !== state.main) mainInput.value = state.main;
    mainInput.classList.toggle("warn", !!state.main.trim() && !main);
    const n = dir.mainCandidates(state.period).length;
    mainHint.className = "hint";
    if (!state.main.trim()) mainHint.textContent = `${n} у списку`;
    else if (!main) { mainHint.className = "hint warn"; mainHint.textContent = "Немає в переліку основних — оберіть зі списку"; }
    else {
      const bits = [`${n} у списку`];
      if (main.formula) bits.push(`формула: ${main.formula}`);
      if (main.pair_flag === 1) bits.push(`пара ${main.pair_text}`);
      mainHint.textContent = bits.join(" · ");
    }
    stBox.checked = !!state.st;
    srBox.checked = !!state.sr;
    srWrap.hidden = state.setting !== SETTING_OUTPATIENT;
    if (shadow.activeElement !== conclusion && conclusion.value !== state.conclusion) conclusion.value = state.conclusion || "";
    conclCount.textContent = `${(state.conclusion || "").length} / 3000`;
    barthelBox.checked = state.opts.barthel !== false;

    plan = L.planSlots(dir, main, state.values);
    renderSlots(main);
    report = L.validate(dir, state.period, state.main, plan.map((s) => s.value), state.st,
      { setting: state.setting, sr: state.sr });
    if (main) { renderAdvice(report, main); renderStatus(report); renderServices(report); renderReport(report); }
    else { adviceBox.replaceChildren(); statusBox.replaceChildren(); servicesBox.replaceChildren(); reportBox.replaceChildren(); }
    fillBtn.disabled = !main;
    save();
  }

  function swap(candName) {
    const r = L.swapMain(dir, state.main, state.values, candName);
    state.main = r.main;
    state.values = r.values;
    mainInput.value = state.main;
    refresh();
  }

  // ------------------------------------------------------------------ події форми
  shadow.addEventListener("input", (e) => {
    const t = e.target;
    if (t === mainInput) state.main = t.value;
    else if (t === conclusion) { state.conclusion = t.value; conclCount.textContent = `${t.value.length} / 3000`; save(); return; }
    else if (t === stBox) state.st = t.checked;
    else if (t === srBox) state.sr = t.checked;
    else if (t === barthelBox) { state.opts.barthel = t.checked; save(); return; }
    else if (Object.values(opt).includes(t)) { Object.assign(state.opts, readOpts()); save(); return; }
    else if (t.dataset && t.dataset.key) state.values[t.dataset.key] = t.value;
    else return;
    const v = (t.value || "").trim();
    if (t.type === "checkbox" || !v || dir.find(v)) refresh(); else save();
  });
  shadow.addEventListener("change", (e) => {
    const t = e.target;
    if (t === mainInput || (t.dataset && t.dataset.key)) refresh();
    if (t === stBox || t === srBox) refresh();
  });
  mainClear.addEventListener("click", () => { state.main = ""; mainInput.value = ""; refresh(); mainInput.focus(); });
  slotsBox.addEventListener("click", (e) => {
    const b = e.target.closest("[data-clear]");
    if (!b || !b.dataset.key) return;
    state.values[b.dataset.key] = "";
    refresh();
    const el = slotsBox.querySelector(`input[data-key="${CSS.escape(b.dataset.key)}"]`);
    if (el) el.focus();
  });
  resetBtn.addEventListener("click", () => {
    Object.assign(state, { main: "", values: {}, conclusion: "", dismissed: [] });
    mainInput.value = ""; conclusion.value = ""; probeOut.replaceChildren();
    refresh();
  });

  function readOpts() {
    return {
      labelText: opt.labelText.value.trim() || "Код діагнозу",
      inputId: opt.inputId.value.trim(),
      timeout: Math.max(1, Number(opt.timeout.value) || 6) * 1000,
      addButtonText: opt.addButtonText.value.trim() || "Додати ще один діагноз",
      typeText: opt.typeText.value.trim() || "Новий діагноз",
      autoAdd: opt.autoAdd.checked,
      barthel: barthelBox.checked,
    };
  }
  function restoreOpts() {
    const o = state.opts || {};
    if (o.labelText) opt.labelText.value = o.labelText;
    if (o.inputId) opt.inputId.value = o.inputId;
    if (o.timeout) opt.timeout.value = o.timeout / 1000;
    if (o.addButtonText) opt.addButtonText.value = o.addButtonText;
    if (o.typeText) opt.typeText.value = o.typeText;
    opt.autoAdd.checked = o.autoAdd !== false;
  }

  probeBtn.addEventListener("click", async () => {
    const res = await fillPage([], { ...readOpts(), dryRun: true });
    probeOut.replaceChildren(
      h("p", null, h("span", { class: res.fields.length ? "l-ok" : "l-fail" }, res.fields.length ? `${OK} ` : `${FAIL} `),
        res.fields.length ? `Знайдено полів «Код діагнозу»: ${res.fields.length} (підсвічено на сторінці)` : "Полів «Код діагнозу» не знайдено"),
      ...res.fields.map((f) => h("p", null, `Поле ${f.index}: ${f.value || "порожнє"}`)));
  });

  // ------------------------------------------------------------------ підтвердження
  function entries() {
    const list = [];
    const push = (text, role) => {
      const t = (text || "").trim();
      if (!t) return;
      const d = dir.find(t);
      list.push({ role, code: d ? d.code : t.split(/\s+/)[0].toUpperCase(), name: d ? d.name : t });
    };
    push(state.main, "Основний");
    plan.forEach((s, i) => push(s.value, `Супутній ${i + 1}`));
    return list;
  }

  fillBtn.addEventListener("click", () => { view = "confirm"; render(); });

  function confirmView() {
    const es = entries();
    const fail = report && report.summary.level === FAIL;
    const lines = fail ? allProblemLines(report, FAIL) : [];
    const barthel = barthelBox.checked;
    const concl = (state.conclusion || "").trim();
    return h("div", { class: "pad" },
      fail
        ? h("div", { class: "problem" }, h("h3", null, report.summary.text),
            h("ul", null, lines.slice(0, 6).map((t) => h("li", null, t))))
        : h("div", { class: "ok-card" }, h("div", { class: "badge" }, tick()),
            report.summary.level === OK ? report.summary.text : "Кодування відповідає формулі (є попередження)"),
      h("div", { class: "confirm" },
        h("h3", null, "Заповнити форму в Askep?"),
        h("dl", { class: "who" },
          h("dt", null, "Основний"), h("dd", null, es[0] ? es[0].name : "—"),
          h("dt", null, "Супутні"), h("dd", null, es.slice(1).map((e) => e.code).join(" · ") || "—"),
          h("dt", null, "Звіт"), h("dd", null, barthel ? `96037-00${concl ? `, заключення (${concl.length} симв.)` : ""}`
            : concl ? `заключення (${concl.length} симв.)` : "не заповнюється"),
          h("dt", null, "Спостереж."), h("dd", null, barthel ? "Barthel_Extended, посилання на звіт" : "не додається")),
        h("p", null, "Помічник заповнить поля на вкладках «Діагнози»" + (barthel || concl ? ", «Діагностичні звіти»" : "") +
          (barthel ? " і «Спостереження»" : "") + ". Нічого не збереже й не підпише — перевірте й збережіть форму самі."),
        h("div", { class: "actions" },
          h("button", { class: "primary", type: "button", onclick: () => startFill() }, fail ? "Так, заповнити попри помилки" : "Так, заповнити"),
          h("button", { class: "secondary", type: "button", onclick: () => { view = "form"; render(); } }, "Скасувати"))));
  }

  // ------------------------------------------------------------------ заповнення
  async function startFill() {
    view = "run";
    run = { steps: [], running: true, fieldsFound: true, error: null };
    render();
    try {
      const res = await fillPage(entries(), {
        ...readOpts(), conclusion: state.conclusion,
        onStep: (step) => { run.steps.push(step); if (view === "run") render(); },
      });
      run.fieldsFound = res.fields.length > 0;
    } catch (e) {
      run.error = e && e.message ? e.message : String(e);
    }
    run.running = false;
    render();
  }

  function stepState(level) { return level === FAIL ? "fail" : level === WARN ? "warn" : "done"; }

  function runView() {
    const items = run.steps.map((s) => h("li", { "data-state": stepState(s.level) },
      h("div", { class: "dot" }, s.level === FAIL ? "!" : s.level === WARN ? "!" : tick()),
      h("span", { class: "label" }, `${s.role}${s.code ? " " + s.code : ""}`),
      h("span", { class: "note" }, s.text)));
    if (run.running) items.push(h("li", { "data-state": "active" }, h("div", { class: "dot" }), h("span", { class: "label" }, "Заповнюю…")));
    const fails = run.steps.filter((s) => s.level === FAIL);
    const warns = run.steps.filter((s) => s.level === WARN);
    let result = null;
    if (!run.running) {
      if (run.error) result = h("div", { class: "problem" }, h("h3", null, "Не вдалося виконати на сторінці"), h("p", null, run.error));
      else if (!run.fieldsFound) result = h("div", { class: "problem" }, h("h3", null, "Полів «Код діагнозу» не знайдено"),
        h("p", null, "Відкрийте форму взаємодії з вкладкою «Діагнози» або перевірте «Налаштування заповнення»."));
      else if (fails.length) result = h("div", { class: "problem" }, h("h3", null, `Не виконано: ${fails.length} ${plural(fails.length, "крок", "кроки", "кроків")}`),
        h("ul", null, fails.map((s) => h("li", null, `${s.role}: ${s.text}`))));
      else if (warns.length) result = h("div", { class: "problem warn" }, h("h3", null, "Перевірте вручну"),
        h("ul", null, warns.map((s) => h("li", null, `${s.role}: ${s.text}`))));
      else result = h("div", { class: "ok-card" }, h("div", { class: "badge" }, tick()), "Форму заповнено");
    }
    return h("div", { class: "pad" },
      h("h3", { class: "view" }, "Заповнення форми"),
      h("ol", { class: "steps" }, items),
      result,
      h("p", { class: "hint" }, run.running
        ? "Не перемикайте вкладку браузера, доки триває заповнення."
        : "Перевірте форму й збережіть її в Askep."),
      run.running ? null : h("button", { class: "secondary", type: "button", onclick: () => { view = "form"; render(); } }, "Повернутися до кодування"));
  }

  // ------------------------------------------------------------------ відмалювання
  function render() {
    const extra = (DATA.sources || []).length - 1;
    footerEl.textContent = `${dir.items.length} ${plural(dir.items.length, "діагноз", "діагнози", "діагнозів")} · ${DATA.source}` +
      (extra > 0 ? ` + ${extra} ${plural(extra, "файл", "файли", "файлів")} НСЗУ` : "");
    footerEl.title = (DATA.sources || [DATA.source]).join("\n");
    if (view === "form") { bodyEl.replaceChildren(formView); refresh(); }
    else { refresh(); bodyEl.replaceChildren(view === "confirm" ? confirmView() : runView()); }
    sheet.querySelectorAll(".seg button").forEach((b) => { b.disabled = view === "run" && run.running; });
  }

  function open() { sheet.hidden = false; launcher.hidden = true; launcher.setAttribute("aria-expanded", "true"); render(); titleEl.focus(); }
  function close() { sheet.hidden = true; launcher.hidden = false; launcher.setAttribute("aria-expanded", "false"); }
  function toggle() { if (sheet.hidden) open(); else close(); }

  globalThis.__askepCoding = { open, close, toggle, shadow, state };

  (async () => {
    const saved = await storage.get();
    if (saved) Object.assign(state, saved, { values: saved.values || {}, opts: saved.opts || {}, dismissed: saved.dismissed || [] });
    delete state.comps;
    restoreOpts();
    mainInput.value = state.main;
    document.body.append(host);
    open();
  })();
})();
