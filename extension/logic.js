/*
 * Логіка кодування (порт coding_rules.py). Дані — directory.json, створений export_json.py.
 * Правила:
 *  - формула (O) застосовується лише до основного та супутнього 1;
 *  - «плюс» — окремі обов'язкові групи, «та/або» і «або» — варіанти в групі (розібрано в Python);
 *  - у кожному випадку обов'язковий Діагноз_Z — коди Z50.x (case_groups у directory.json); СФЗ — необов'язкова;
 *  - група виконана самим діагнозом, якщо він має відповідну категорію;
 *  - у випадаючому списку — лише категорії ще не закритих вимог.
 * Файл працює і в браузері (глобальний об'єкт RehabLogic), і в Node (module.exports) — для тестів.
 */
(function (root) {
  "use strict";

  const CATS = ["ПП", "ФО", "С", "СП", "СФЗ", "Z"];   // Z — Діагноз_Z (Z50.x), окремо від СФЗ
  const PERIOD_POST = "Післягострий";
  const PERIOD_LONG = "Довготривалий";
  const SETTING_INPATIENT = "Стаціонар";
  const SETTING_OUTPATIENT = "Амбулаторія";
  const OK = "✔", WARN = "⚠", FAIL = "✖", INFO = "ℹ";

  const normCode = (c) => c.replace(/[АВСЕНКМОРТХІ]/g, (ch) => "ABCEHKMOPTXI"["АВСЕНКМОРТХІ".indexOf(ch)]);
  const clean = (s) => String(s ?? "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();

  // ---------------------------------------------------------------- токени
  // Набір токенів (категорії I–M і коди) з префіксами кодів: S06 ↔ S06.20, R47 ↔ R47.0
  class TokenSet {
    constructor(tokens) {
      this.exact = new Set(tokens);
      this.prefixes = new Set();
      for (const t of this.exact) {
        if (t.length > 3 && /^\d\d$/.test(t.slice(1, 3))) {
          this.prefixes.add(t.slice(0, 3));
          if (t.length > 5) this.prefixes.add(t.slice(0, 5));
        }
      }
    }
  }
  const asTS = (t) => (t instanceof TokenSet ? t : new TokenSet(t));
  const codeMatches = (code, ts) =>
    ts.exact.has(code) || ts.exact.has(code.slice(0, 3)) || ts.exact.has(code.slice(0, 5)) ||
    ts.exact.has(code.slice(0, 6)) || ts.prefixes.has(code);

  // ---------------------------------------------------------------- діагноз
  const condInPeriod = (n, period) =>
    !((period === PERIOD_LONG && n.includes("післягостр")) || (period === PERIOD_POST && n.includes("довготрив")));
  const condConditional = (n) => ["якщо", "допустим", "після операц"].some((k) => n.includes(k));
  const prepGroup = (g) => { g.ts = new TokenSet(g.tokens); return g; };

  function prepare(item) {
    item.catSet = new Set(item.cats);
    item.cats_text = CATS.filter((c) => item.catSet.has(c)).join(", ") || "немає в I–M";
    let conds;
    if (Array.isArray(item.main_conds)) conds = item.main_conds.map((c) => c.toLowerCase());
    else {
      const n = item.main_text.toLowerCase();
      conds = n.startsWith("так") || n.startsWith("допустимі") ? [n] : [];
    }
    item.conds = conds;
    item.can_be_main = conds.length > 0;
    item.conditional = conds.length > 0 && conds.every(condConditional);
    item.groups.forEach(prepGroup);
    if (item.comp_groups) item.comp_groups.forEach(prepGroup);
    item.cgroups = item.comp_groups || item.groups;
    item.comp_formula = item.comp_formula || "";
    item.source = item.source || "довідник";
    return item;
  }

  function mainInPeriod(d, period) {
    return d.conds.some((n) => condInPeriod(n, period));
  }

  function matches(d, tokens) {
    const ts = asTS(tokens);
    for (const c of d.catSet) if (ts.exact.has(c)) return true;
    return codeMatches(d.code, ts);
  }

  const allTokens = (d) => d.groups.flatMap((g) => g.tokens);

  // ---------------------------------------------------------------- довідник
  class Directory {
    constructor(data) {
      this.items = data.items.map(prepare);
      this.exclusions = data.exclusions;
      this.caseGroups = (data.case_groups || []).map(prepGroup);
      this.sources = data.sources || [data.source];
      this.ambulatory = data.ambulatory || null;
      if (this.ambulatory) for (const s of this.ambulatory.services) s.ts = new TokenSet(s.codes.map(normCode));
      this.source = data.source;
      this.generated = data.generated;
      this.byName = new Map(this.items.map((d) => [d.name, d]));
      this.byCode = new Map();
      for (const d of this.items) if (!this.byCode.has(d.code)) this.byCode.set(d.code, d);
    }

    // діагноз поза довідником, введений з кодом МКХ: враховується лише за кодом (пари †/*, переліки кодів)
    adhoc(text) {
      const t = clean(text);
      const m = t.match(/^([A-ZА-ЯІ]\d{2}(?:\.\d{1,2})?)(?![\d.])/);
      if (!m) return null;
      return prepare({ name: t, code: normCode(m[1]), mark: "", cats: [], main_text: "", main_conds: null,
        formula: "", comp_formula: "", groups: [], comp_groups: null, pair_tokens: [], pair_text: "", pair_flag: 0,
        source: "введено", row: -1 });
    }

    find(text) {
      const t = clean(text);
      if (!t) return null;
      return this.byName.get(t) || this.byCode.get(normCode(t)) || null;
    }

    mainCandidates(period) {
      return this.items.filter((d) => mainInPeriod(d, period));
    }

    formulaGroups(main, slot, selected) {
      const groups = main.groups.map((g) => [main, g]);
      if (slot > 0 && selected[0]) groups.push(...selected[0].cgroups.map((g) => [selected[0], g]));
      return groups;
    }

    companionTokens(main, slot, selected, narrow = true) {
      const formula = this.formulaGroups(main, slot, selected);
      let own = formula.filter(([o, g]) => !matches(o, g.ts));
      if (!own.length) own = formula;
      own = own.concat(this.caseGroups.map((g) => [main, g]));
      let use = own;
      if (narrow) {
        const others = [main, ...selected.filter((d, j) => j !== slot && d)];
        // умови супутнього 1 закриваються лише супутніми (основний не враховується)
        const unmet = own.filter(([o, g]) => !others.some((x) => x !== o && !(o !== main && x === main) && matches(x, g.ts)));
        if (unmet.length) use = unmet;
      }
      const tokens = use.flatMap(([, g]) => g.tokens).concat(main.pair_tokens);
      for (const d of selected.slice(0, slot)) if (d) tokens.push(...d.pair_tokens);
      return new TokenSet(tokens);
    }

    companionCandidates(main, slot, selected, narrow = true) {
      if (!main) return [];
      const tokens = this.companionTokens(main, slot, selected, narrow);
      const excl = new Set([main.name, ...selected.slice(0, slot).filter(Boolean).map((d) => d.name)]);
      return this.items.filter((d) => !excl.has(d.name) && matches(d, tokens));
    }
  }

  // ---------------------------------------------------------------- перевірка
  const line = (level, text) => ({ level, text });
  const groupMet = (g, others) => others.some((o) => matches(o, g.ts));

  function groupLine(g, met, stRequired, prefix, selfD) {
    if (selfD && matches(selfD, g.ts)) {
      const own = CATS.filter((c) => selfD.catSet.has(c) && g.tokens.includes(c)).join(", ") || selfD.code;
      return line(OK, `${prefix}${g.text} — виконано самим діагнозом (${own}), додатковий не потрібен`);
    }
    if (met) return line(OK, `${prefix}${g.text} — виконано`);
    if (g.kind === "code" && !stRequired)
      return line(WARN, `${prefix}${g.text} — рекомендовано додати (CR_2_6, CR_5_6, CR_8_2, CR_11_2)`);
    return line(FAIL, `${prefix}бракує: ${g.text}`);
  }

  function pairLine(d, others) {
    if (d.pair_flag === 0) return null;
    if (d.pair_flag === 2) return line(WARN, "Потрібен парний код †/* — у переліку пар не вказано який, перевірте вручну");
    if (others.some((o) => matches(o, d.pair_tokens))) return line(OK, `Парний код †/* є (${d.pair_text})`);
    if (d.pair_flag === 1) return line(FAIL, `Додайте парний код †/*: ${d.pair_text}`);
    return line(WARN, `Рекомендовано парний код: ${d.pair_text}`);
  }

  // ---------------------------------------------------------------- амбулаторія: послуги АР (порт ambulatory_lines)
  const coefText = (x) => x.toFixed(1).replace(".", ",");
  function serviceLabel(s, sr) {
    if (s.id === "AP12") return sr ? `АР1 (коеф. ${coefText(s.coef_sr)})` : `АР2 (коеф. ${coefText(s.coef_no_sr)})`;
    return `${s.name} (коеф. ${coefText(s.coef)})`;
  }
  function ambulatoryLines(amb, main, comps, sr) {
    const out = [];
    for (const s of amb.services) {
      const label = serviceLabel(s, sr);
      const hits = [...new Set(comps.filter((c) => codeMatches(c.code, s.ts)).map((c) => c.code))];
      if (codeMatches(main.code, s.ts)) out.push(line(OK, `${label}: основний діагноз ${main.code} є в переліку`));
      else if (hits.length)
        out.push(line(WARN, `${label}: у переліку лише супутній ${hits.join(", ")} — уточніть, чи достатньо супутнього («щонайменше один з переліку»)`));
      else { out.push(line(FAIL, `${label}: жодного діагнозу випадку немає в переліку`)); continue; }
      for (const n of s.notes || []) out.push(line(INFO, `    ${n}`));
    }
    for (const n of amb.general_notes || []) out.push(line(INFO, n));
    return out;
  }

  function validate(dir, period, mainText, companionTexts, stRequired = false, opts = {}) {
    const rep = { main: [], main_groups: [], companions: [], exclusions: [], summary: line(INFO, ""), services: [] };
    const main = mainText ? dir.find(mainText) : null;
    // позиції зберігаються: супутній 1 — це перше поле, навіть якщо воно порожнє
    const compsRaw = [...companionTexts];
    const comps = compsRaw.map((c) => (clean(c) ? dir.find(c) || dir.adhoc(c) : null));

    if (!main) {
      rep.main.push(line(FAIL, "Основний діагноз не обрано або не знайдено в довіднику"));
      rep.summary = line(FAIL, "Оберіть основний діагноз");
      return rep;
    }

    rep.main.push(line(INFO, `${main.name}  |  категорії: ${main.cats_text}`));
    rep.main.push(line(INFO, `Формула: ${main.formula || "—"}`));
    if (main.source === "НСЗУ" && main.row === 0)
      rep.main.push(line(INFO, "Кода немає в довіднику — назву й категорії взято з батьківської рубрики"));
    if (!main.can_be_main) rep.main.push(line(FAIL, "Не може бути основним (стовпець N)"));
    else if (!mainInPeriod(main, period))
      rep.main.push(line(FAIL, `Не може бути основним у періоді «${period}» (стовпець N: ${main.main_text})`));
    else if (main.conditional) rep.main.push(line(WARN, `Умовно допустимий: ${main.main_text}`));
    else rep.main.push(line(OK, "Може бути основним"));

    const known = comps.filter(Boolean);
    const pl = pairLine(main, known);
    if (pl) rep.main.push(pl);

    [...main.groups, ...dir.caseGroups].forEach((g, i) =>
      rep.main_groups.push(groupLine(g, groupMet(g, known), stRequired, `Група ${i + 1}: `, main)));

    const seen = [];
    compsRaw.forEach((txt, i) => {
      if (!clean(txt)) return;
      const d = comps[i];
      const lines = [];
      if (!d) {
        lines.push(line(INFO, "Немає в довіднику (коморбідний стан) — у формулах не враховується"));
        rep.companions.push([clean(txt), lines]);
        return;
      }
      if (d.source === "введено") {
        if (matches(d, dir.companionTokens(main, i, comps, false)))
          lines.push(line(OK, `Немає в довіднику — враховано за кодом ${d.code}: відповідає формулі`));
        else lines.push(line(INFO, `Немає в довіднику (коморбідний стан) — враховано лише за кодом ${d.code}`));
        rep.companions.push([d.name, lines]);
        return;
      }
      lines.push(line(INFO, `Категорії: ${d.cats_text}`));
      if (d.name === main.name) lines.push(line(FAIL, "Збігається з основним"));
      if (seen.includes(d.name)) lines.push(line(FAIL, "Повтор"));
      seen.push(d.name);

      const allowed = dir.companionCandidates(main, i, comps, false);
      if (allowed.some((a) => a.name === d.name))
        lines.push(line(OK, `Відповідає ${i === 0 ? "формулі основного" : "формулам основного та супутнього 1"}`));
      else if (d.catSet.has("СФЗ"))
        lines.push(line(INFO, "СФЗ — допустимий як додатковий, у формулах не враховується"));
      else if (d.name !== main.name)
        lines.push(line(WARN, `Не передбачено ${i === 0 ? "формулою основного" : "формулами основного та супутнього 1"} (допустимо лише як супутній стан)`));

      const others = [main, ...comps.filter((c, j) => j !== i && c)];
      if (i === 0) {
        lines.push(line(INFO, `Формула: ${d.comp_formula || d.formula || "—"}`));
        d.cgroups.forEach((g, k) =>
          lines.push(groupLine(g, groupMet(g, others.slice(1)), stRequired, `Його група ${k + 1}: `, d)));   // без основного
      }
      const p = pairLine(d, others);
      if (p) lines.push(p);
      rep.companions.push([d.name, lines]);
    });

    const codes = [main.code, ...known.map((c) => c.code)];
    for (const [a, b, sev, rule, expl] of dir.exclusions)
      if (codes.some((x) => x.startsWith(a)) && codes.some((x) => x.startsWith(b)))
        rep.exclusions.push(line(sev, `${a} + ${b} (${rule}): ${expl}`));

    const levels = [...rep.main, ...rep.main_groups, ...rep.exclusions, ...rep.companions.flatMap(([, l]) => l)]
      .map((l) => l.level);
    if (opts.setting === SETTING_OUTPATIENT && dir.ambulatory)
      rep.services = ambulatoryLines(dir.ambulatory, main, known, !!opts.sr);
    if (!mainInPeriod(main, period)) rep.summary = line(FAIL, "Основний діагноз некоректний");
    else if (levels.includes(FAIL)) rep.summary = line(FAIL, "Кодування не відповідає правилам — виправте пункти «✖»");
    else if (levels.includes(WARN))
      rep.summary = line(WARN, "Кодування відповідає формулі, але є попередження — перевірте пункти «⚠»");
    else rep.summary = line(OK, "Кодування відповідає формулі та правилам");
    return rep;
  }

  // ---------------------------------------------------------------- план полів супутніх (порт plan_slots)
  const ROLE_TITLES = { main: "За формулою основного", pair: "Пара †/*",
    comp1: "За формулою супутнього 1", free: "Додатковий (необов'язково)" };
  const MAX_SLOTS = 12;

  function slotCandidates(dir, main, slots, index) {
    if (!main) return [];
    const s = slots[index];
    const taken = new Set([main.name, ...slots.filter((x, j) => j !== index && x.diag).map((x) => x.diag.name)]);
    if (s.tokens === null) return dir.items.filter((d) => !taken.has(d.name));
    const ts = new TokenSet(s.tokens);
    return dir.items.filter((d) => !taken.has(d.name) && matches(d, ts));
  }

  function slotFits(slot) {
    if (!slot.diag || slot.tokens === null) return null;
    return matches(slot.diag, new TokenSet(slot.tokens));
  }

  function planSlots(dir, main, values) {
    if (!main) return [];
    const mk = (key, role, label, tokens) => {
      const v = values[key] || "";
      const d = clean(v) ? dir.find(v) || dir.adhoc(v) : null;
      return { key, role, label, tokens, value: v, diag: d };
    };
    const slots = [];
    const groups = main.groups.filter((g) => !matches(main, g.ts))
      .concat(dir.caseGroups.filter((g) => !matches(main, g.ts)));
    groups.forEach((g, i) => slots.push(mk(`m${i}`, "main", `${ROLE_TITLES.main}: ${g.text}`, [...g.tokens])));
    const mainSlots = [...slots];
    const freeVals = Array.from({ length: MAX_SLOTS }, (_, i) => mk(`f${i}`, "free", "", null));
    const freeDiags = freeVals.filter((s) => s.diag).map((s) => s.diag);

    const addPairs = (owners, pool) => {
      for (const [key, owner] of owners) {
        if (!owner || owner.pair_flag !== 1 || !owner.pair_tokens.length) continue;
        const ts = new TokenSet(owner.pair_tokens);
        const own = new Set(owner.pair_tokens);
        const same = slots.find((s) => s.role === "pair" && s.tokens.length === own.size && s.tokens.every((t) => own.has(t)));
        if (same) {
          if (!same.label.includes(owner.code)) same.label = same.label.replace(":", `, ${owner.code}:`);
          continue;
        }
        const needed = !pool.some((x) => x !== owner && matches(x, ts));
        if (needed || clean(values[`p:${key}`] || ""))
          slots.push(mk(`p:${key}`, "pair", `${ROLE_TITLES.pair} для ${owner.code}: ${owner.pair_text}`, [...owner.pair_tokens]));
      }
    };
    const base = [main, ...mainSlots.filter((s) => s.diag).map((s) => s.diag), ...freeDiags];
    addPairs([["main", main], ...mainSlots.map((s) => [s.key, s.diag])], base);

    const willCover = (g) => slots.some((s, i) => {
      if (s.role !== "pair" || s.diag) return false;
      const cand = slotCandidates(dir, main, slots, i);
      return cand.length > 0 && cand.every((d) => matches(d, g.ts));
    });

    const c1 = mainSlots.length ? mainSlots[0].diag : null;
    const compSlots = [];
    if (c1) {
      const pool = slots.filter((s) => s.diag && s.key !== "m0").map((s) => s.diag).concat(freeDiags);
      c1.cgroups.forEach((g, k) => {
        const covered = matches(c1, g.ts) || pool.some((x) => matches(x, g.ts)) || willCover(g);
        if (covered && !clean(values[`c${k}`] || "")) return;
        const s = mk(`c${k}`, "comp1", `${ROLE_TITLES.comp1} (${c1.code}): ${g.text}`, [...g.tokens]);
        slots.push(s);
        compSlots.push(s);
      });
      if (compSlots.length) {
        const base2 = [main, ...slots.filter((s) => s.diag).map((s) => s.diag), ...freeDiags];
        addPairs(compSlots.map((s) => [s.key, s.diag]), base2);
      }
    }

    const filled = freeVals.map((s, i) => (s.diag || clean(s.value) ? i : -1)).filter((i) => i >= 0);
    const nFree = Math.min(MAX_SLOTS - slots.length, filled.length ? Math.max(...filled) + 2 : 1);
    for (let i = 0; i < Math.max(0, nFree); i++) {
      freeVals[i].label = ROLE_TITLES.free;
      slots.push(freeVals[i]);
    }
    return slots;
  }

  const api = { CATS, PERIOD_POST, PERIOD_LONG, SETTING_INPATIENT, SETTING_OUTPATIENT, OK, WARN, FAIL, INFO, Directory, validate, matches, mainInPeriod,
    planSlots, slotCandidates, slotFits, ROLE_TITLES };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.RehabLogic = api;
})(typeof self !== "undefined" ? self : this);
