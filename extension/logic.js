/*
 * Логіка кодування (порт coding_rules.py). Дані — directory.json, створений export_json.py.
 * Правила:
 *  - формула (O) застосовується лише до основного та супутнього 1;
 *  - «плюс» і «та/або» — окремі обов'язкові групи, «або» — один із варіантів (розібрано в Python);
 *  - група виконана самим діагнозом, якщо він має відповідну категорію;
 *  - у випадаючому списку — лише категорії ще не закритих вимог.
 * Файл працює і в браузері (глобальний об'єкт RehabLogic), і в Node (module.exports) — для тестів.
 */
(function (root) {
  "use strict";

  const CATS = ["ПП", "ФО", "С", "СП", "СФЗ"];
  const PERIOD_POST = "Післягострий";
  const PERIOD_LONG = "Довготривалий";
  const OK = "✔", WARN = "⚠", FAIL = "✖", INFO = "ℹ";

  const clean = (s) => String(s ?? "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();

  // ---------------------------------------------------------------- діагноз
  function prepare(item) {
    item.catSet = new Set(item.cats);
    item.cats_text = CATS.filter((c) => item.catSet.has(c)).join(", ") || "немає в I–M";
    const n = item.main_text.toLowerCase();
    item.can_be_main = n.startsWith("так") || n.startsWith("допустимі");
    item.conditional = item.can_be_main && ["якщо", "допустим", "після операц"].some((k) => n.includes(k));
    return item;
  }

  function mainInPeriod(d, period) {
    if (!d.can_be_main) return false;
    const n = d.main_text.toLowerCase();
    if (period === PERIOD_LONG && n.includes("післягостр")) return false;
    if (period === PERIOD_POST && n.includes("довготрив")) return false;
    return true;
  }

  function matches(d, tokens) {
    const t = tokens instanceof Set ? tokens : new Set(tokens);
    for (const c of d.catSet) if (t.has(c)) return true;
    return [3, 5, 6].some((n) => t.has(d.code.slice(0, n)));
  }

  const allTokens = (d) => d.groups.flatMap((g) => g.tokens);

  // ---------------------------------------------------------------- довідник
  class Directory {
    constructor(data) {
      this.items = data.items.map(prepare);
      this.exclusions = data.exclusions;
      this.source = data.source;
      this.generated = data.generated;
      this.byName = new Map(this.items.map((d) => [d.name, d]));
      this.byCode = new Map();
      for (const d of this.items) if (!this.byCode.has(d.code)) this.byCode.set(d.code, d);
    }

    find(text) {
      const t = clean(text);
      if (!t) return null;
      return this.byName.get(t) || this.byCode.get(t) || null;
    }

    mainCandidates(period) {
      return this.items.filter((d) => mainInPeriod(d, period));
    }

    formulaGroups(main, slot, selected) {
      const groups = main.groups.map((g) => [main, g]);
      if (slot > 0 && selected[0]) groups.push(...selected[0].groups.map((g) => [selected[0], g]));
      return groups;
    }

    companionTokens(main, slot, selected, narrow = true) {
      let own = this.formulaGroups(main, slot, selected).filter(([o, g]) => !matches(o, g.tokens));
      if (!own.length) own = this.formulaGroups(main, slot, selected);
      let use = own;
      if (narrow) {
        const others = [main, ...selected.filter((d, j) => j !== slot && d)];
        const unmet = own.filter(([o, g]) => !others.some((x) => x !== o && matches(x, g.tokens)));
        if (unmet.length) use = unmet;
      }
      const tokens = use.flatMap(([, g]) => g.tokens).concat(main.pair_tokens);
      for (const d of selected.slice(0, slot)) if (d) tokens.push(...d.pair_tokens);
      return new Set(tokens);
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
  const groupMet = (g, others) => others.some((o) => matches(o, g.tokens));

  function groupLine(g, met, stRequired, prefix, selfD) {
    if (selfD && matches(selfD, g.tokens)) {
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
    if (d.pair_flag === 2) return line(WARN, "Потрібен парний код †/* — у довіднику не вказано який, перевірте вручну");
    if (others.some((o) => matches(o, d.pair_tokens))) return line(OK, `Парний код †/* є (${d.pair_text})`);
    if (d.pair_flag === 1) return line(FAIL, `Додайте парний код †/*: ${d.pair_text}`);
    return line(WARN, `Рекомендовано парний код: ${d.pair_text}`);
  }

  function validate(dir, period, mainText, companionTexts, stRequired = false) {
    const rep = { main: [], main_groups: [], companions: [], exclusions: [], summary: line(INFO, "") };
    const main = mainText ? dir.find(mainText) : null;
    const compsRaw = companionTexts.filter((c) => clean(c));
    const comps = compsRaw.map((c) => dir.find(c));

    if (!main) {
      rep.main.push(line(FAIL, "Основний діагноз не обрано або не знайдено в довіднику"));
      rep.summary = line(FAIL, "Оберіть основний діагноз");
      return rep;
    }

    rep.main.push(line(INFO, `${main.name}  |  категорії: ${main.cats_text}`));
    rep.main.push(line(INFO, `Формула: ${main.formula || "—"}`));
    if (!main.can_be_main) rep.main.push(line(FAIL, "Не може бути основним (стовпець N)"));
    else if (!mainInPeriod(main, period))
      rep.main.push(line(FAIL, `Не може бути основним у періоді «${period}» (стовпець N: ${main.main_text})`));
    else if (main.conditional) rep.main.push(line(WARN, `Умовно допустимий: ${main.main_text}`));
    else rep.main.push(line(OK, "Може бути основним"));

    const known = comps.filter(Boolean);
    const pl = pairLine(main, known);
    if (pl) rep.main.push(pl);

    main.groups.forEach((g, i) =>
      rep.main_groups.push(groupLine(g, groupMet(g, known), stRequired, `Група ${i + 1}: `, main)));
    if (!main.groups.length) rep.main_groups.push(line(INFO, "Формула не містить вимог"));

    const seen = [];
    compsRaw.forEach((txt, i) => {
      const d = comps[i];
      const lines = [];
      if (!d) {
        lines.push(line(INFO, "Немає в довіднику (коморбідний стан) — у формулах не враховується"));
        rep.companions.push([clean(txt), lines]);
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
        lines.push(line(INFO, `Формула: ${d.formula || "—"}`));
        d.groups.forEach((g, k) =>
          lines.push(groupLine(g, groupMet(g, others), stRequired, `Його група ${k + 1}: `, d)));
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
    if (!mainInPeriod(main, period)) rep.summary = line(FAIL, "Основний діагноз некоректний");
    else if (levels.includes(FAIL)) rep.summary = line(FAIL, "Кодування не відповідає правилам — виправте пункти «✖»");
    else if (levels.includes(WARN))
      rep.summary = line(WARN, "Кодування відповідає формулі, але є попередження — перевірте пункти «⚠»");
    else rep.summary = line(OK, "Кодування відповідає формулі та правилам");
    return rep;
  }

  const api = { CATS, PERIOD_POST, PERIOD_LONG, OK, WARN, FAIL, INFO, Directory, validate, matches, mainInPeriod };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.RehabLogic = api;
})(typeof self !== "undefined" ? self : this);
