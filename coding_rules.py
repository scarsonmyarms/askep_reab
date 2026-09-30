"""
Логіка кодування діагнозів реабілітаційного випадку.

Джерела:
  * Додаток до наказу НСЗУ (таблиця xlsx): стовпці B (діагноз), I–M (ПП, ФО, С, СП, СФЗ),
    N (чи може бути основним), O (формула кодування);
  * Правила щодо визначення послуг за напрямом реабілітаційної допомоги
    (наказ НСЗУ № 182 від 16.04.2026) — період, подвійне кодування †/*, несумісні поєднання.

Правила застосування формул:
  * формула (O) застосовується лише до основного діагнозу та супутнього 1;
  * список супутнього 1 — за формулою основного; списки супутніх 2..N — за формулами основного
    та супутнього 1 (плюс парні коди †/* уже обраних супутніх);
  * у список потрапляють лише категорії ще не закритих вимог (групи, закриті категорією самого
    діагнозу або вже обраними діагнозами, не враховуються); коли все закрито — показуються всі
    категорії формул, які діагнози не закривають самі;
  * кожне «плюс» — окрема обов'язкова група; «та/або» сприймається як «та» (кожна категорія —
    окрема обов'язкова група); «або» — достатньо одного з варіантів;
  * група вважається виконаною самим діагнозом, якщо він має відповідну категорію (I–M)
    (напр., G93.7 з категоріями ПП, ФО і формулою «плюс ФО» додаткових діагнозів не потребує).

Запуск з командного рядка (без графічного інтерфейсу):
  python coding_rules.py довідник.xlsx --period post --main I63.3 --comp G81.9 --comp R47
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from typing import Iterable

from openpyxl import load_workbook

CATS = ("ПП", "ФО", "С", "СП", "СФЗ")
PERIOD_POST = "Післягострий"
PERIOD_LONG = "Довготривалий"

OK, WARN, FAIL, INFO = "✔", "⚠", "✖", "ℹ"

# ----------------------------------------------------------------------------------------
# Несумісні поєднання (Правила CR_3_5, CR_4_3, CR_6_3 / табл. 1). Можна доповнювати.
# (префікс коду 1, префікс коду 2, серйозність, правило, пояснення)
# ----------------------------------------------------------------------------------------
EXCLUSIONS: list[tuple[str, str, str, str, str]] = []
for _b in ["M51.1", "M47.2", "M50.1", "S24.2", "S14.2", "S34.2"]:
    EXCLUSIONS.append(("M54.1", _b, FAIL, "CR_3_5",
                       "Не слід одночасно застосовувати M54.1 з кодом, що вже містить ознаку радикулопатії / "
                       "ураження корінця; перевага — коду, що відображає етіологію та обмеження."))
EXCLUSIONS.append(("M54.1", "G54", WARN, "CR_3_5",
                   "Одночасне застосування M54.1 з кодами типу G54* не рекомендується (подвійне кодування)."))
for _a in ["M43.3", "M47.1", "M50.0"]:
    for _b in ["G99.2", "G95.9"]:
        EXCLUSIONS.append((_a, _b, WARN, "CR_4_3",
                           "Комбінований код уже містить мієлопатію — додаткове кодування мієлопатії не здійснюється."))
for _a in ["M32.1", "M34", "M35.3", "M10", "M11", "M00", "M01", "M02", "M07", "M45.0", "M46.1", "M05", "M06"]:
    EXCLUSIONS.append((_a, "M13", FAIL, "CR_6_3, табл. 1",
                       "Комбінований код уже включає артрит/артропатію — додаткове кодування артриту (M13) не здійснюється."))

# ----------------------------------------------------------------------------------------
# Розбір текстів
# ----------------------------------------------------------------------------------------
_CAT_RE = re.compile(r"Діагноз\s*_\s*(ПП|ФО|СФЗ|СП|С)(?![А-ЯІЇЄA-Z])")
_ST_RE = re.compile(r"([ST]\d{2}(?:\.\d)?)(?:\s*-\s*([ST]\d{2}(?:\.\d)?))?\.?-?")
_LEAD_RE = re.compile(r"^\s*([A-ZН]\d{2}(?:\.\d+)?)\.?\s*([*†])?")
_REF_RE = re.compile(r"([A-Z]\d{2}(?:\.\d+)?)(?:\s*-\s*([A-Z]\d{2}(?:\.\d+)?))?\s*\.?\s*-?\s*([*†])?")


def _clean(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").replace("\xa0", " ")).strip()


def _expand_st(a: str, b: str) -> list[str]:
    if not b:
        return [a]
    if "." not in a and "." not in b:
        return [f"{a[0]}{i:02d}" for i in range(int(a[1:3]), int(b[1:3]) + 1)]
    return [f"{a[:3]}.{i}" for i in range(int(a[4]), int(b[4]) + 1)]


def _expand_any(a: str, b: str) -> list[str]:
    if not b:
        return [a]
    if "." in a or "." in b:
        if a[:3] == b[:3]:
            return [f"{a[:3]}.{i}" for i in range(int(a[4]), int(b[4]) + 1)]
        a, b = a[:3], b[:3]
    out, letter = [], ord(a[0])
    while letter <= ord(b[0]):
        lo = int(a[1:3]) if letter == ord(a[0]) else 0
        hi = int(b[1:3]) if letter == ord(b[0]) else 99
        out += [f"{chr(letter)}{i:02d}" for i in range(lo, hi + 1)]
        letter += 1
    return out


def _readable(tok: str) -> str:
    return f"Діагноз_{tok}" if tok in CATS else tok


@dataclass
class Group:
    kind: str                 # "cat" — категорії I–M; "code" — коди S/T, прямо названі у формулі
    tokens: list[str]

    @property
    def text(self) -> str:
        t = " або ".join(_readable(x) for x in self.tokens)
        return t + (" (код первинної травми/опіку)" if self.kind == "code" else "")


def parse_formula(formula: str) -> tuple[list[Group], bool]:
    """Повертає групи формули та ознаку «*-код»."""
    f = re.sub(r"^\s*плюс\s*", "", _clean(formula))
    parts: list[str] = []
    for p in re.split(r"\s*плюс\s*", f):
        for q in re.split(r"\s+та\s+(?=код)", p):
            parts += re.split(r"\s*та\s*/\s*або\s*", q)      # «та/або» = «та»
    groups, star = [], False
    for p in parts:
        if "*-код" in p:
            star, p = True, p.replace("*-код", "")
        cats = _CAT_RE.findall(p)
        codes: list[str] = []
        for a, b in _ST_RE.findall(_CAT_RE.sub("", p)):
            codes += _expand_st(a, b)
        toks = list(dict.fromkeys(cats + codes))
        if toks:
            groups.append(Group("code" if codes and not cats else "cat", toks))
    return groups, star


# ----------------------------------------------------------------------------------------
# Модель
# ----------------------------------------------------------------------------------------
@dataclass
class Diagnosis:
    row: int
    name: str
    code: str
    mark: str                       # "*", "†" або ""
    cats: set[str]
    main_text: str                  # стовпець N
    formula: str                    # стовпець O
    groups: list[Group] = field(default_factory=list)
    pair_tokens: list[str] = field(default_factory=list)
    pair_text: str = ""
    pair_flag: int = 0              # 0 — не потрібно; 1 — обов'язково; 2 — ручна перевірка; 3 — рекомендовано

    @property
    def can_be_main(self) -> bool:
        n = self.main_text.lower()
        return n.startswith("так") or n.startswith("допустимі")

    @property
    def conditional(self) -> bool:
        n = self.main_text.lower()
        return self.can_be_main and any(k in n for k in ("якщо", "допустим", "після операц"))

    def main_in_period(self, period: str | None) -> bool:
        if not self.can_be_main:
            return False
        n = self.main_text.lower()
        if period == PERIOD_LONG and "післягостр" in n:
            return False
        if period == PERIOD_POST and "довготрив" in n:
            return False
        return True

    @property
    def cats_text(self) -> str:
        return ", ".join(c for c in CATS if c in self.cats) or "немає в I–M"

    def matches(self, tokens: Iterable[str]) -> bool:
        """Чи підходить діагноз під набір токенів (категорії I–M або префікси кодів)."""
        toks = set(tokens)
        if self.cats & toks:
            return True
        return any(self.code[:n] in toks for n in (3, 5, 6))

    def all_tokens(self) -> list[str]:
        return [t for g in self.groups for t in g.tokens]


class Directory:
    """Довідник діагнозів із таблиці xlsx."""

    def __init__(self, path: str, sheet: str | None = None):
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet] if sheet else self._find_sheet(wb)
        rows = list(ws.iter_rows(values_only=True))
        hdr_i, col = self._find_header(rows)
        self.items: list[Diagnosis] = []
        seen: set[str] = set()
        raw = []
        for i in range(hdr_i + 1, len(rows)):
            r = rows[i]
            name = _clean(r[col["B"]] if col["B"] < len(r) else "")
            if not name or name in seen:
                continue
            seen.add(name)
            raw.append((i + 1, r, name))
        # коди з позначкою * (для визначення парних кодів)
        star_codes = set()
        for _, _, name in raw:
            m = _LEAD_RE.match(name)
            if m and m.group(2) == "*":
                star_codes.add(m.group(1))
        for rownum, r, name in raw:
            get = lambda k: _clean(r[col[k]]) if col[k] < len(r) and r[col[k]] is not None else ""
            m = _LEAD_RE.match(name)
            mark = (m.group(2) or "") if m else ""
            code = m.group(1) if m else name.split(" ")[0]
            cats = {c for c, k in zip(CATS, "IJKLM") if get(k).lower() == "так"}
            groups, star_formula = parse_formula(get("O"))
            d = Diagnosis(rownum, name, code, mark, cats, get("N"), get("O"), groups)
            self._set_pair(d, name[m.end():] if m else name, star_formula, star_codes)
            self.items.append(d)
        self.by_name = {d.name: d for d in self.items}

    @staticmethod
    def _find_sheet(wb):
        for ws in wb.worksheets:
            for r in ws.iter_rows(min_row=1, max_row=10, values_only=True):
                if any(isinstance(v, str) and "Діагноз_ПП" in v for v in r):
                    return ws
        return wb.worksheets[0]

    @staticmethod
    def _find_header(rows):
        names = {"B": "Діагноз", "I": "Діагноз_ПП", "J": "Діагноз_ФО", "K": "Діагноз_С", "L": "Діагноз_СП",
                 "M": "Діагноз_СФЗ", "N": "Основний діагноз", "O": "Формула для кодування"}
        default = {k: ord(k) - ord("A") for k in names}
        for i, r in enumerate(rows[:20]):
            vals = [_clean(v) for v in r]
            if "Діагноз_ПП" in vals:
                col = dict(default)
                for k, h in names.items():
                    if h in vals:
                        col[k] = vals.index(h)
                return i, col
        return 3, default

    @staticmethod
    def _set_pair(d: Diagnosis, rest: str, star_formula: bool, star_codes: set[str]):
        """Парні коди †/* (розділ III Правил) з назви діагнозу."""
        startype = d.mark == "*" or (star_formula and d.mark != "†")
        toks, raw = [], []
        for a, b, mk in _REF_RE.findall(rest):
            if mk == "†" and not startype:
                continue
            if startype or mk == "*" or (not mk and a in star_codes):
                toks += _expand_any(a, b)
                raw.append(a + ("–" + b if b else "") + (mk or ("*" if a in star_codes else "")))
        d.pair_tokens = list(dict.fromkeys(toks))
        d.pair_text = ", ".join(raw) if raw else ""
        if d.mark in ("*", "†") or star_formula:
            d.pair_flag = 1 if toks else 2
        else:
            d.pair_flag = 3 if toks else 0

    # --------------------------- пошук ---------------------------
    def find(self, text: str) -> Diagnosis | None:
        """Точна назва або код (напр. «I63.3»)."""
        text = _clean(text)
        if text in self.by_name:
            return self.by_name[text]
        for d in self.items:
            if d.code == text:
                return d
        return None

    # --------------------------- списки ---------------------------
    def main_candidates(self, period: str | None) -> list[Diagnosis]:
        return [d for d in self.items if d.main_in_period(period)]

    @staticmethod
    def _formula_groups(main: Diagnosis, slot: int, selected: list[Diagnosis | None]):
        """Групи формул, що стосуються поля slot: групи основного, а для полів 2+ — ще й супутнього 1.
        Повертає [(власник, група)]."""
        groups = [(main, g) for g in main.groups]
        if slot > 0 and selected and selected[0] is not None:
            groups += [(selected[0], g) for g in selected[0].groups]
        return groups

    def companion_tokens(self, main: Diagnosis, slot: int, selected: list[Diagnosis | None],
                         narrow: bool = True) -> list[str]:
        """
        Токени для поля slot.
          * Групи, які власник формули закриває сам (своєю категорією), не враховуються.
          * narrow=True (для випадаючого списку): лише групи, ще не закриті іншими обраними
            діагнозами; якщо все закрито — усі незакриті самим власником групи.
          * narrow=False (для перевірки): усі незакриті самим власником групи.
        Парні коди †/* основного та попередніх супутніх додаються завжди.
        """
        own = [(o, g) for o, g in self._formula_groups(main, slot, selected) if not o.matches(g.tokens)]
        if not own:   # усі вимоги закриває сам діагноз — додаткові не обов'язкові
            own = self._formula_groups(main, slot, selected)
        use = own
        if narrow:
            others = [main] + [d for j, d in enumerate(selected) if j != slot and d is not None]
            unmet = [(o, g) for o, g in own if not any(x is not o and x.matches(g.tokens) for x in others)]
            if unmet:
                use = unmet
        tokens = [t for _, g in use for t in g.tokens] + main.pair_tokens
        for d in selected[:slot]:
            if d is not None:
                tokens += d.pair_tokens
        return tokens

    def companion_candidates(self, main: Diagnosis | None, slot: int,
                             selected: list[Diagnosis | None], narrow: bool = True) -> list[Diagnosis]:
        """slot — 0-базовий номер поля; selected — обрані супутні (у порядку полів)."""
        if main is None:
            return []
        tokens = self.companion_tokens(main, slot, selected, narrow)
        excl = {main.name} | {d.name for d in selected[:slot] if d is not None}
        return [d for d in self.items if d.name not in excl and d.matches(tokens)]


# ----------------------------------------------------------------------------------------
# Перевірка
# ----------------------------------------------------------------------------------------
@dataclass
class Line:
    level: str      # ✔ ⚠ ✖ ℹ
    text: str


@dataclass
class Report:
    main: list[Line] = field(default_factory=list)
    main_groups: list[Line] = field(default_factory=list)
    companions: list[tuple[str, list[Line]]] = field(default_factory=list)
    exclusions: list[Line] = field(default_factory=list)
    summary: Line = field(default_factory=lambda: Line(INFO, ""))

    def all_lines(self) -> list[Line]:
        out = self.main + self.main_groups + self.exclusions
        for _, ls in self.companions:
            out += ls
        return out

    def as_text(self) -> str:
        s = ["ОСНОВНИЙ ДІАГНОЗ"] + [f"  {l.level} {l.text}" for l in self.main]
        s += ["", "ФОРМУЛА ОСНОВНОГО"] + [f"  {l.level} {l.text}" for l in self.main_groups]
        s += ["", "СУПУТНІ"]
        for i, (name, ls) in enumerate(self.companions, 1):
            s.append(f"  {i}. {name}")
            s += [f"     {l.level} {l.text}" for l in ls]
        s += ["", "НЕСУМІСНІ ПОЄДНАННЯ"] + ([f"  {l.level} {l.text}" for l in self.exclusions] or [f"  {OK} Не виявлено"])
        s += ["", f"ПІДСУМОК: {self.summary.level} {self.summary.text}"]
        return "\n".join(s)


def _group_met(g: Group, others: list[Diagnosis]) -> bool:
    return any(o.matches(g.tokens) for o in others)


def _group_line(g: Group, met: bool, st_required: bool, prefix: str = "", self_d: Diagnosis | None = None) -> Line:
    if self_d is not None and self_d.matches(g.tokens):
        own = ", ".join(c for c in CATS if c in self_d.cats and c in g.tokens) or self_d.code
        return Line(OK, f"{prefix}{g.text} — виконано самим діагнозом ({own}), додатковий не потрібен")
    if met:
        return Line(OK, f"{prefix}{g.text} — виконано")
    if g.kind == "code" and not st_required:
        return Line(WARN, f"{prefix}{g.text} — рекомендовано додати (CR_2_6, CR_5_6, CR_8_2, CR_11_2)")
    return Line(FAIL, f"{prefix}бракує: {g.text}")


def _pair_line(d: Diagnosis, others: list[Diagnosis]) -> Line | None:
    if d.pair_flag == 0:
        return None
    if d.pair_flag == 2:
        return Line(WARN, "Потрібен парний код †/* — у довіднику не вказано який, перевірте вручну")
    if any(o.matches(d.pair_tokens) for o in others):
        return Line(OK, f"Парний код †/* є ({d.pair_text})")
    if d.pair_flag == 1:
        return Line(FAIL, f"Додайте парний код †/*: {d.pair_text}")
    return Line(WARN, f"Рекомендовано парний код: {d.pair_text}")


def validate(directory: Directory, period: str, main_text: str, companion_texts: list[str],
             st_required: bool = False) -> Report:
    """
    period          — PERIOD_POST або PERIOD_LONG;
    main_text       — назва або код основного діагнозу;
    companion_texts — назви/коди супутніх (порожні рядки ігноруються; діагноз поза довідником
                      вважається коморбідним станом і у формулах не враховується);
    st_required     — чи є коди S/T у формулах наслідків (T90–T95) обов'язковими.
    """
    rep = Report()
    main = directory.find(main_text) if main_text else None
    comps_raw = [c for c in companion_texts if _clean(c)]
    comps = [directory.find(c) for c in comps_raw]

    if main is None:
        rep.main.append(Line(FAIL, "Основний діагноз не обрано або не знайдено в довіднику"))
        rep.summary = Line(FAIL, "Оберіть основний діагноз")
        return rep

    # --- основний
    rep.main.append(Line(INFO, f"{main.name}  |  категорії: {main.cats_text}"))
    rep.main.append(Line(INFO, f"Формула: {main.formula or '—'}"))
    if not main.can_be_main:
        rep.main.append(Line(FAIL, "Не може бути основним (стовпець N)"))
    elif not main.main_in_period(period):
        rep.main.append(Line(FAIL, f"Не може бути основним у періоді «{period}» (стовпець N: {main.main_text})"))
    elif main.conditional:
        rep.main.append(Line(WARN, f"Умовно допустимий: {main.main_text}"))
    else:
        rep.main.append(Line(OK, "Може бути основним"))

    known = [c for c in comps if c is not None]
    pl = _pair_line(main, known)
    if pl:
        rep.main.append(pl)

    # --- формула основного: групи закриваються супутніми
    for i, g in enumerate(main.groups, 1):
        rep.main_groups.append(_group_line(g, _group_met(g, known), st_required, f"Група {i}: ", main))
    if not main.groups:
        rep.main_groups.append(Line(INFO, "Формула не містить вимог"))

    # --- супутні
    seen: list[str] = []
    for i, (txt, d) in enumerate(zip(comps_raw, comps)):
        lines: list[Line] = []
        if d is None:
            lines.append(Line(INFO, "Немає в довіднику (коморбідний стан) — у формулах не враховується"))
            rep.companions.append((_clean(txt), lines))
            continue
        lines.append(Line(INFO, f"Категорії: {d.cats_text}"))
        if d.name == main.name:
            lines.append(Line(FAIL, "Збігається з основним"))
        if d.name in seen:
            lines.append(Line(FAIL, "Повтор"))
        seen.append(d.name)

        allowed = directory.companion_candidates(main, i, comps, narrow=False)
        if any(a.name == d.name for a in allowed):
            src = "формулі основного" if i == 0 else "формулам основного та супутнього 1"
            lines.append(Line(OK, f"Відповідає {src}"))
        elif "СФЗ" in d.cats:
            lines.append(Line(INFO, "СФЗ — допустимий як додатковий, у формулах не враховується"))
        elif d.name != main.name:
            src = "формулою основного" if i == 0 else "формулами основного та супутнього 1"
            lines.append(Line(WARN, f"Не передбачено {src} (допустимо лише як супутній стан)"))

        others = [main] + [c for j, c in enumerate(comps) if j != i and c is not None]
        if i == 0:   # власна формула — лише для супутнього 1
            lines.append(Line(INFO, f"Формула: {d.formula or '—'}"))
            for k, g in enumerate(d.groups, 1):
                lines.append(_group_line(g, _group_met(g, others), st_required, f"Його група {k}: ", d))
        pl = _pair_line(d, others)
        if pl:
            lines.append(pl)
        rep.companions.append((d.name, lines))

    # --- несумісні поєднання
    codes = [main.code] + [c.code for c in known]
    for a, b, sev, rule, expl in EXCLUSIONS:
        if any(x.startswith(a) for x in codes) and any(x.startswith(b) for x in codes):
            rep.exclusions.append(Line(sev, f"{a} + {b} ({rule}): {expl}"))

    # --- підсумок
    levels = [l.level for l in rep.all_lines()]
    if not main.main_in_period(period):
        rep.summary = Line(FAIL, "Основний діагноз некоректний")
    elif FAIL in levels:
        rep.summary = Line(FAIL, "Кодування не відповідає правилам — виправте пункти «✖»")
    elif WARN in levels:
        rep.summary = Line(WARN, "Кодування відповідає формулі, але є попередження — перевірте пункти «⚠»")
    else:
        rep.summary = Line(OK, "Кодування відповідає формулі та правилам")
    return rep


# ----------------------------------------------------------------------------------------
def _cli():
    ap = argparse.ArgumentParser(description="Перевірка кодування діагнозів реабілітаційного випадку")
    ap.add_argument("xlsx", help="файл довідника (Додаток до наказу)")
    ap.add_argument("--period", choices=["post", "long"], default="post",
                    help="post — післягострий, long — довготривалий")
    ap.add_argument("--main", required=True, help="основний діагноз (код або повна назва)")
    ap.add_argument("--comp", action="append", default=[], help="супутній діагноз (можна повторювати)")
    ap.add_argument("--st-required", action="store_true", help="коди S/T у формулах T9x — обов'язкові")
    ap.add_argument("--list", action="store_true", help="показати список для наступного супутнього поля")
    a = ap.parse_args()
    d = Directory(a.xlsx)
    period = PERIOD_POST if a.period == "post" else PERIOD_LONG
    print(validate(d, period, a.main, a.comp, a.st_required).as_text())
    if a.list:
        main = d.find(a.main)
        sel = [d.find(c) for c in a.comp]
        cand = d.companion_candidates(main, len(sel), sel)
        print(f"\nСписок для супутнього {len(sel) + 1}: {len(cand)} діагнозів")
        for x in cand[:30]:
            print("  ", x.name)
        if len(cand) > 30:
            print("   …")


if __name__ == "__main__":
    _cli()