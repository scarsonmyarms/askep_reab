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
 * Нічого не зберігає і не надсилає — лише заповнює поля; збереження форми виконує користувач.
 */
async function askepFillDiagnoses(entries, opts) {
  const o = Object.assign(
    {
      labelText: "Код діагнозу", placeholder: "Оберіть", inputId: "", timeout: 6000, dryRun: false,
      autoAdd: true, addButtonText: "Додати ще один діагноз",
      typeLabel: "Тип діагнозу", typeText: "Новий діагноз",
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

  // ---------------------------------------------------------------- основний сценарій
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
  return { fields: state, results };
}
