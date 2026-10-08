/*
 * Функція, яку popup впроваджує на сторінку Askep (chrome.scripting.executeScript).
 * Має бути самодостатньою: жодних посилань на змінні поза нею.
 *
 * Пошук полів: за підписом «Код діагнозу» береться перше текстове поле після нього
 * (id на кшталт input-297 генерується сторінкою і змінюється, тому не є основним орієнтиром;
 * його можна задати в налаштуваннях як додатковий).
 * Заповнення: введення коду в поле пошуку → очікування списку → вибір варіанта з точним кодом.
 * Якщо вільних полів бракує — натискає кнопку «Додати ще один діагноз», у новому блоці вибирає
 * «Тип діагнозу» = «Новий діагноз» (без цього поле коду не з'являється) і чекає на поле коду.
 * Порожній «Тип діагнозу» в уже наявних блоках теж заповнюється «Новим діагнозом».
 * Якщо вказано conclusion — на вкладці «Діагностичні звіти» заповнюється «Заключення лікаря».
 * Якщо увімкнено barthel: після діагнозів — вкладка «Діагностичні звіти» (код 96037-00, заключення), потім
 * «Спостереження» (перемикач «Загальні спостереження (LOINC)», категорія «Шкали оцінки, опитування»,
 * вид Barthel_Extended, посилання на звіт 96037-00).
 * Нічого не зберігає і не надсилає — лише заповнює поля; збереження форми виконує користувач.
 */
async function askepFillDiagnoses(entries, opts) {
  const o = Object.assign(
    {
      labelText: "Код діагнозу", placeholder: "Оберіть", inputId: "", timeout: 6000, dryRun: false,
      autoAdd: true, addButtonText: "Додати ще один діагноз",
      typeLabel: "Тип діагнозу", typeText: "Новий діагноз",
      // вкладки та шкала Бартел
      diagTab: "Діагнози", reportsTab: "Діагностичні звіти", obsTab: "Спостереження",
      barthel: false, reportCode: "96037-00",
      obsRadio: "Загальні спостереження (LOINC)",
      obsCategory: "Шкали оцінки, опитування",
      refLabel: "Посилання на діагностичний звіт",
      conclusion: "", conclusionLabel: "Заключення лікаря",
      obsSearch: "Barthel_Extended", obsType: "Barthel_Extended - Підсумкова оцінка Індекс Бартел (розширений)",
    },
    opts || {}
  );
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const norm = (s) => String(s || "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
  const visible = (el) => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden";
  const TEXT_INPUT = 'input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"]):not([type="button"])';
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // код як окреме слово: «R47» не збігається з «R47.0», але збігається з «R47.» чи «R47 Розлади»
  const codeRe = (code) => new RegExp(`(^|[\\s(\\[])${esc(code)}(?=[\\s)\\]*†,:;-]|\\.(?!\\d)|$)`);

  // ---------------------------------------------------------------- пошук полів
  const docOrder = (a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1);

  // поля, підписані текстом labelText: для кожного підпису — перше текстове поле після нього
  function findByLabel(labelText) {
    const fields = [];
    const inputs = [...document.querySelectorAll(TEXT_INPUT)].filter(visible);
    const labels = [...document.querySelectorAll("label, legend, span, div, p, strong")].filter((el) => {
      const t = norm(el.textContent);
      if (!t.startsWith(labelText) || t.length > 120) return false;
      return ![...el.children].some((ch) => norm(ch.textContent).startsWith(labelText));   // найглибший елемент
    });
    for (const lb of labels) {
      const inp = inputs.find((i) => lb.compareDocumentPosition(i) & Node.DOCUMENT_POSITION_FOLLOWING);
      if (inp && !fields.includes(inp)) fields.push(inp);
    }
    return fields.sort(docOrder);
  }

  function findFields() {
    const fields = findByLabel(o.labelText);
    const add = (el) => { if (el && visible(el) && !fields.includes(el)) fields.push(el); };
    if (o.inputId) add(document.getElementById(o.inputId));
    if (!fields.length && o.placeholder)
      [...document.querySelectorAll(TEXT_INPUT)].filter((i) => visible(i) && i.placeholder === o.placeholder).forEach(add);
    return fields.sort(docOrder);
  }

  function currentValue(input) {
    const box = input.closest(".v-input, .v-field, .v-autocomplete, .v-select") || input.parentElement;
    const sel = box && box.querySelector(
      ".v-select__selection, .v-select__selection-text, .v-autocomplete__selection, .v-chip__content"
    );
    return norm(sel ? sel.textContent : input.value);
  }

  // ---------------------------------------------------------------- взаємодія з полем
  const setValue = (input, v) => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, v);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  };
  const mouse = (el) => {
    for (const t of ["mousedown", "mouseup", "click"])
      el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window }));
  };
  const key = (el, k) => {
    for (const t of ["keydown", "keyup"])
      el.dispatchEvent(new KeyboardEvent(t, { key: k, bubbles: true }));
  };

  function visibleOptions() {
    const sel = [
      ".menuable__content__active .v-list-item",
      ".v-menu__content--active .v-list-item",
      ".v-overlay--active .v-list-item",
      '[role="listbox"] [role="option"]',
    ].join(",");
    return [...document.querySelectorAll(sel)].filter(visible);
  }

  async function pick(input, code) {
    input.scrollIntoView({ block: "center" });
    const slot = input.closest(".v-input__slot, .v-field") || input;
    mouse(slot);
    input.focus();
    setValue(input, "");
    await sleep(80);
    setValue(input, code);
    key(input, code.slice(-1));

    const re = codeRe(code);
    const t0 = Date.now();
    let opts = [];
    while (Date.now() - t0 < o.timeout) {
      await sleep(200);
      opts = visibleOptions();
      const exact = opts.find((el) => re.test(norm(el.textContent)));
      if (exact) {
        const text = norm(exact.textContent);
        mouse(exact);
        await sleep(400);
        const now = currentValue(input);
        key(input, "Escape");
        input.blur();
        return re.test(now)
          ? { level: "✔", text: `вибрано: ${text}` }
          : { level: "⚠", text: `варіант «${text}» натиснуто, але поле не підтвердило вибір — перевірте` };
      }
    }
    key(input, "Escape");
    input.blur();
    if (opts.length)
      return { level: "⚠", text: `точного варіанта з кодом ${code} немає (варіантів: ${opts.length}) — оберіть вручну` };
    return { level: "⚠", text: `список варіантів не з'явився за ${o.timeout / 1000} с — оберіть вручну` };
  }

  // ---------------------------------------------------------------- додавання блоку діагнозу
  function findAddButton() {
    const want = norm(o.addButtonText).toLowerCase();
    return [...document.querySelectorAll("button, [role=button], a.v-btn")]
      .filter(visible)
      .find((b) => !b.disabled && norm(b.textContent).toLowerCase().includes(want));
  }

  // «Тип діагнозу» — випадаючий список: відкрити й вибрати варіант із точним текстом o.typeText
  async function selectType(input) {
    const want = norm(o.typeText).toLowerCase();
    input.scrollIntoView({ block: "center" });
    mouse(input.closest(".v-input__slot, .v-field") || input);
    input.focus();
    const t0 = Date.now();
    while (Date.now() - t0 < o.timeout) {
      await sleep(200);
      const opt = visibleOptions().find((el) => norm(el.textContent).toLowerCase() === want);
      if (opt) {
        mouse(opt);
        await sleep(300);
        key(input, "Escape");
        input.blur();
        return norm(currentValue(input)).toLowerCase() === want;
      }
    }
    key(input, "Escape");
    input.blur();
    return false;
  }

  // порожні «Тип діагнозу» в наявних блоках → «Новий діагноз»; повертає кількість заповнених
  async function ensureTypes() {
    let n = 0;
    for (const t of findByLabel(o.typeLabel)) {
      if (currentValue(t)) continue;
      if (await selectType(t)) n++;
    }
    return n;
  }

  async function waitFreshCodeField(known) {
    const t0 = Date.now();
    while (Date.now() - t0 < o.timeout) {
      const fresh = findFields().filter((f) => !known.includes(f) && !currentValue(f));
      if (fresh.length) return fresh[0];
      await sleep(250);
    }
    return null;
  }

  async function addField(known) {
    const btn = findAddButton();
    if (!btn) return { error: `кнопку «${o.addButtonText}» не знайдено` };
    const typesBefore = findByLabel(o.typeLabel);
    btn.scrollIntoView({ block: "center" });
    btn.click();

    // новий блок: чекаємо на порожній «Тип діагнозу» і вибираємо «Новий діагноз»
    let typeField = null;
    const t0 = Date.now();
    while (Date.now() - t0 < o.timeout) {
      await sleep(250);
      const fresh = findFields().filter((f) => !known.includes(f) && !currentValue(f));
      if (fresh.length) return { field: fresh[0] };          // поле коду з'явилося одразу
      typeField = findByLabel(o.typeLabel).find((t) => !typesBefore.includes(t) && !currentValue(t));
      if (typeField) break;
    }
    if (!typeField) return { error: `після натискання «${o.addButtonText}» новий блок діагнозу не з'явився` };
    if (!(await selectType(typeField)))
      return { error: `у новому блоці не вдалося вибрати «${o.typeLabel}» = «${o.typeText}»` };
    const field = await waitFreshCodeField(known);
    return field ? { field } : { error: `після вибору «${o.typeText}» поле «${o.labelText}» не з'явилося` };
  }

  // ---------------------------------------------------------------- вкладки
  function findTab(name) {
    const want = norm(name).toLowerCase();
    return [...document.querySelectorAll('[role="tab"]')].filter(visible)
      .find((t) => norm(t.textContent).toLowerCase() === want);
  }

  async function openTab(name) {
    const tab = findTab(name);
    if (!tab) return { ok: false, missing: true };
    if (tab.getAttribute("aria-selected") !== "true") {
      tab.scrollIntoView({ block: "center" });
      mouse(tab);
      for (let i = 0; i < 30 && tab.getAttribute("aria-selected") !== "true"; i++) await sleep(150);
    }
    await sleep(500);                                   // вміст вкладки встигає відмалюватися
    return { ok: tab.getAttribute("aria-selected") === "true" };
  }

  // поля-списки активної вкладки («Оберіть»), у порядку документа
  function selectInputs(readonly) {
    const root = document.querySelector(".v-window-item--active") || document;
    return [...root.querySelectorAll('input[placeholder="Оберіть"], .v-select input[type="text"]')]
      .filter((i, k, a) => visible(i) && a.indexOf(i) === k && (readonly === undefined || i.readOnly === readonly));
  }

  // відкрити список поля (за потреби — ввести пошук) і вибрати варіант, що проходить test
  async function choose(input, { search = null, test, prefer = null, timeout = o.timeout }) {
    input.scrollIntoView({ block: "center" });
    mouse(input.closest(".v-input__slot, .v-field") || input);
    input.focus();
    if (search !== null && !input.readOnly) {
      setValue(input, "");
      await sleep(80);
      setValue(input, search);
      key(input, search.slice(-1));
    }
    const t0 = Date.now();
    let opts = [];
    while (Date.now() - t0 < timeout) {
      await sleep(200);
      opts = visibleOptions();
      const ok = opts.filter((el) => test(norm(el.textContent)));
      if (ok.length) {
        const el = prefer ? prefer(ok) : ok[0];
        const text = norm(el.textContent);
        mouse(el);
        await sleep(400);
        const now = currentValue(input);
        key(input, "Escape");
        input.blur();
        return { ok: true, text, confirmed: test(now) };
      }
    }
    key(input, "Escape");
    input.blur();
    await sleep(150);
    return { ok: false, count: opts.length };
  }

  // серед полів-кандидатів знайти те, у списку якого є потрібний варіант
  async function chooseAmong(cands, args) {
    for (const inp of cands) {
      const r = await choose(inp, { ...args, timeout: Math.min(o.timeout, 4000) });
      if (r.ok) return { ...r, input: inp };
    }
    return { ok: false };
  }

  const dateOf = (t) => {
    const m = t.match(/(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}):(\d{2}))?/);
    return m ? new Date(+m[3], +m[2] - 1, +m[1], +(m[4] || 0), +(m[5] || 0)).getTime() : 0;
  };
  const latest = (els) => els.reduce((a, b) => (dateOf(norm(b.textContent)) > dateOf(norm(a.textContent)) ? b : a));
  const res = (role, level, text) => ({ role, code: "", name: "", level, text });

  // власний текст елемента (без тексту кнопок і інших вкладених елементів), напр. «Заключення лікаря»
  const ownText = (el) => norm([...el.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.textContent).join(" "));

  // поле під заголовком (v-subheader / label) з точним текстом — у межах його колонки .col
  function fieldByHeading(text, selector = 'input[placeholder="Оберіть"], .v-select input[type="text"]') {
    const want = norm(text).toLowerCase();
    const root = document.querySelector(".v-window-item--active") || document;
    const head = [...root.querySelectorAll(".v-subheader, label, legend")].filter(visible)
      .find((h) => ownText(h).toLowerCase() === want || norm(h.textContent).toLowerCase() === want);
    if (!head) return null;
    const box = head.closest(".col, [class*='col-']") || head.parentElement;
    const inside = box && [...box.querySelectorAll(selector)].find(visible);
    if (inside) return inside;
    return [...root.querySelectorAll(selector)].filter(visible)
      .find((i) => head.compareDocumentPosition(i) & Node.DOCUMENT_POSITION_FOLLOWING) || null;
  }

  // «Заключення лікаря»: заповнюється лише порожнє поле (наявний текст не перезаписується)
  async function fillConclusion() {
    const role = "Заключення лікаря";
    const text = String(o.conclusion || "").trim();
    if (!text) return res(role, "⚠", "у розширенні не вказано — поле на сторінці обов'язкове");
    const ta = fieldByHeading(o.conclusionLabel, "textarea");
    if (!ta) return res(role, "✖", `поле «${o.conclusionLabel}» не знайдено`);
    const cur = norm(ta.value);
    if (cur === norm(text)) return res(role, "ℹ", "уже заповнено цим текстом");
    if (cur) return res(role, "⚠", "поле вже містить інший текст — не змінено, перевірте вручну");
    ta.scrollIntoView({ block: "center" });
    ta.focus();
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set.call(ta, text.slice(0, 3000));
    ta.dispatchEvent(new Event("input", { bubbles: true }));
    ta.dispatchEvent(new Event("change", { bubbles: true }));
    ta.blur();
    await sleep(200);
    const short = text.length > 60 ? text.slice(0, 60) + "…" : text;
    return norm(ta.value) === norm(text.slice(0, 3000))
      ? res(role, "✔", `заповнено: «${short}»` + (text.length > 3000 ? " (обрізано до 3000 символів)" : ""))
      : res(role, "⚠", "текст введено, але поле його не прийняло — перевірте");
  }

  // перемикач (radio) за текстом підпису, напр. «Загальні спостереження (LOINC)»
  async function chooseRadio(text) {
    const want = norm(text).toLowerCase();
    const root = document.querySelector(".v-window-item--active") || document;
    const label = [...root.querySelectorAll("label")].filter(visible)
      .find((l) => norm(l.textContent).toLowerCase() === want);
    if (!label) return { ok: false };
    const input = (label.htmlFor && document.getElementById(label.htmlFor)) ||
      (label.closest(".v-radio") || label.parentElement).querySelector('input[type="radio"]');
    const checked = () => input && (input.checked || input.getAttribute("aria-checked") === "true");
    if (checked()) return { ok: true, already: true };
    label.scrollIntoView({ block: "center" });
    label.click();
    for (let i = 0; i < 15 && !checked(); i++) await sleep(150);
    if (!checked() && input) {
      input.click();
      for (let i = 0; i < 15 && !checked(); i++) await sleep(150);
    }
    await sleep(400);                                   // поля форми можуть з'явитися після вибору
    return { ok: checked() };
  }

  // ---------------------------------------------------------------- шкала Бартел: звіт 96037-00 + спостереження
  async function barthelSteps() {
    const out = [];
    const code = o.reportCode;
    const codeTest = (t) => t.includes(code);

    // 1) Діагностичні звіти: код 96037-00
    const tr = await openTab(o.reportsTab);
    if (!tr.ok) return [res("Діагностичний звіт", "✖", `вкладку «${o.reportsTab}» не знайдено або не відкрилася`)];
    const filled = selectInputs(false).find((i) => codeTest(currentValue(i)));
    if (filled) out.push(res("Діагностичний звіт", "ℹ", `${code} уже вказано`));
    else {
      const r = await chooseAmong(selectInputs(false).filter((i) => !currentValue(i)), { search: code, test: codeTest });
      out.push(r.ok
        ? res("Діагностичний звіт", r.confirmed ? "✔" : "⚠", r.confirmed ? `вибрано: ${r.text}` : `«${r.text}» натиснуто, але поле не підтвердило вибір — перевірте`)
        : res("Діагностичний звіт", "✖", `поле з варіантом ${code} не знайдено — додайте звіт вручну`));
      if (!r.ok) return out;
    }

    out.push(await fillConclusion());                     // «Заключення лікаря» — перед спостереженнями

    // 2) Спостереження: категорія → вид → посилання на звіт
    const to = await openTab(o.obsTab);
    if (!to.ok) return [...out, res("Спостереження", "✖", `вкладку «${o.obsTab}» не знайдено або не відкрилася`)];
    if (o.obsRadio) {
      const rr = await chooseRadio(o.obsRadio);
      if (!rr.ok) return [...out, res("Спостереження: тип", "✖", `перемикач «${o.obsRadio}» не знайдено або не вибрався`)];
      out.push(res("Спостереження: тип", rr.already ? "ℹ" : "✔", rr.already ? `«${o.obsRadio}» уже вибрано` : `вибрано: ${o.obsRadio}`));
    }
    const cat = norm(o.obsCategory).toLowerCase();
    const catDone = selectInputs(true).find((i) => currentValue(i).toLowerCase() === cat);
    if (catDone) out.push(res("Спостереження: категорія", "ℹ", `«${o.obsCategory}» уже вибрано`));
    else {
      const r = await chooseAmong(selectInputs(true).filter((i) => !currentValue(i)), { test: (t) => t.toLowerCase() === cat });
      out.push(r.ok ? res("Спостереження: категорія", r.confirmed ? "✔" : "⚠", `вибрано: ${r.text}`)
                    : res("Спостереження: категорія", "✖", `не вдалося вибрати «${o.obsCategory}»`));
      if (!r.ok) return out;
      await sleep(500);
    }
    const typ = norm(o.obsType).toLowerCase();
    const typeTest = (t) => t.toLowerCase().startsWith(typ) || t.toLowerCase() === typ;
    let typeInput = selectInputs(false).find((i) => typeTest(currentValue(i)));
    if (typeInput) out.push(res("Спостереження: вид", "ℹ", "Barthel_Extended уже вибрано"));
    else {
      const r = await chooseAmong(selectInputs(false).filter((i) => !currentValue(i)), { search: o.obsSearch, test: typeTest });
      out.push(r.ok ? res("Спостереження: вид", r.confirmed ? "✔" : "⚠", `вибрано: ${r.text}`)
                    : res("Спостереження: вид", "✖", `варіант «${o.obsType}» не знайдено`));
      if (!r.ok) return out;
      typeInput = r.input;
      await sleep(500);
    }
    const refTest = (t) => t.includes(`(${code})`);
    const refInput = fieldByHeading(o.refLabel);         // лише поле «Посилання на діагностичний звіт»
    if (!refInput) out.push(res("Спостереження: посилання", "✖", `поле «${o.refLabel}» не знайдено`));
    else if (refTest(currentValue(refInput))) out.push(res("Спостереження: посилання", "ℹ", "посилання на звіт уже вказано"));
    else {
      const r = await choose(refInput, { test: refTest, prefer: latest });
      out.push(r.ok ? res("Спостереження: посилання", r.confirmed ? "✔" : "⚠", `вибрано: ${r.text}`)
                    : res("Спостереження: посилання", "✖",
                          `у списку немає звіту (${code}) — можливо, звіт треба спершу зберегти; оберіть вручну`));
    }
    return out;
  }

  // ---------------------------------------------------------------- основний сценарій
  const diagTab = findTab(o.diagTab);
  if (diagTab) await openTab(o.diagTab);              // спершу — вкладка «Діагнози» (якщо вкладки є)
  const typed = o.dryRun ? 0 : await ensureTypes();
  if (typed) await sleep(400);
  const fields = findFields();
  const state = fields.map((f, i) => ({ index: i + 1, value: currentValue(f) }));

  if (o.dryRun) {
    fields.forEach((f) => {
      const box = f.closest(".v-input") || f;
      const prev = box.style.outline;
      box.style.outline = "3px solid #26c6ca";
      setTimeout(() => (box.style.outline = prev), 2500);
    });
    return { fields: state, results: [] };
  }

  const results = [];
  const free = fields.filter((f, i) => !state[i].value);
  for (const e of entries) {
    const re = codeRe(e.code);
    const already = state.find((s) => re.test(s.value));
    if (already) {
      results.push({ ...e, level: "ℹ", text: `уже є на сторінці (поле ${already.index})` });
      continue;
    }
    let field = free.shift();
    if (!field && o.autoAdd) {
      const added = await addField(fields);
      if (added.error) {
        results.push({ ...e, level: "✖", text: `${added.error} — додайте блок вручну й натисніть «Заповнити» ще раз` });
        continue;
      }
      field = added.field;
      fields.push(field);
    }
    if (!field) {
      results.push({ ...e, level: "✖", text: "немає вільного поля — додайте блок діагнозу на сторінці й натисніть «Заповнити» ще раз" });
      continue;
    }
    const r = await pick(field, e.code);
    results.push({ ...e, field: fields.indexOf(field) + 1, ...r });
  }
  if (o.barthel) results.push(...(await barthelSteps()));
  else if (String(o.conclusion || "").trim()) {           // без Бартел — лише заключення на вкладці звітів
    const tr = await openTab(o.reportsTab);
    results.push(tr.ok || tr.missing ? await fillConclusion()
                                     : res("Заключення лікаря", "✖", `вкладка «${o.reportsTab}» не відкрилася`));
  }
  return { fields: state, results };
}
