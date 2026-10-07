"""
Завантаження нових файлів НСЗУ (джерела формул, пар †/* і переліку основних діагнозів).

Файли шукаються в тій самій папці, що й довідник, за ключовими словами в назві:
  * «Перелік основних діагнозів»                         → перелік основних і умови використання;
  * «Співвідношення коду основного діагнозу та формули…»  → формули для діагнозу в ролі основного;
  * «Співвідношення коду додаткового діагнозу та формули…» → формули для діагнозу в ролі супутнього;
  * «Перелік пар діагнозів хрестик та зірочка»           → пари †/*;
  * «Перелік діагнозів ПП, ФО, С, СП, Z»                  → категорії кодів (ПП, ФО, С, СП, СФЗ, Z).

Формули записано булевою мовою: «Діагноз_ПП AND (Діагноз_ФО OR Діагноз_С) AND Діагноз_Z»,
переліки кодів у дужках — «один із». «Діагноз_Z» — окрема категорія (коди Z50.x «реабілітаційні процедури»), не СФЗ.

Якщо код є і в рядку групи (рубрики), і окремо (напр., G54.2 у групі G54 і окремим рядком),
діє рядок, де рубрика коду представлена найвужче (точніший запис).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

# кириличні літери, схожі на латинські, у кодах МКХ (напр., «М76», «Н54.0» у довіднику)
_CYR2LAT = str.maketrans("АВСЕНКМОРТХІ", "ABCEHKMOPTXI")
_CODE_RE = re.compile(r"[A-ZА-ЯІЇЄ]\d{2}(?:\.\d{1,2})?")
CAT_MAP = {"ПП": "ПП", "ФО": "ФО", "С": "С", "СП": "СП", "СФЗ": "СФЗ", "Z": "Z"}   # Діагноз_Z — окрема категорія (Z50.x)


def norm_code(c: str) -> str:
    return c.strip().translate(_CYR2LAT)


def codes_in(text) -> list[str]:
    return [norm_code(c) for c in _CODE_RE.findall(str(text or "").replace("\xa0", " "))]


def _clean(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").replace("\xa0", " ")).strip()


def read_rows(path: str) -> list[tuple]:
    ws = load_workbook(path, read_only=True, data_only=True).worksheets[0]
    out = []
    for r in ws.iter_rows(values_only=True):
        if any(v not in (None, "") for v in r):
            out.append(r)
    return out[1:]          # без заголовка


# ------------------------------------------------------------------------------ пошук файлів
@dataclass
class NszuFiles:
    main_list: str | None = None
    formulas_main: str | None = None
    formulas_add: str | None = None
    pairs: str | None = None
    categories: str | None = None

    def _all(self):
        return (self.main_list, self.formulas_main, self.formulas_add, self.pairs, self.categories)

    def any(self) -> bool:
        return any(self._all())

    def describe(self) -> list[str]:
        return [Path(p).name for p in self._all() if p]


def find_files(folder: str | Path) -> NszuFiles:
    f = NszuFiles()
    for p in sorted(Path(folder).glob("*.xlsx")):
        n = p.name.lower().replace("_", " ")
        if n.startswith("~$"):
            continue
        if "співвідношення" in n and "коду додатков" in n:
            f.formulas_add = str(p)
        elif "співвідношення" in n and "коду основн" in n:
            f.formulas_main = str(p)
        elif "пар" in n and ("хрестик" in n or "зірочк" in n):
            f.pairs = str(p)
        elif "перелік" in n and "основн" in n:
            f.main_list = str(p)
        elif "перелік діагнозів" in n and ("пп" in n or "фо" in n):
            f.categories = str(p)
    return f


# ------------------------------------------------------------------------------ формули
def _split_top(s: str, op: str) -> list[str]:
    out, depth, cur, i, sep = [], 0, "", 0, f" {op} "
    while i < len(s):
        ch = s[i]
        depth += (ch == "(") - (ch == ")")
        if depth == 0 and s.startswith(sep, i):
            out.append(cur)
            cur, i = "", i + len(sep)
            continue
        cur += ch
        i += 1
    out.append(cur)
    return [x.strip() for x in out if x.strip()]


def _strip_parens(s: str) -> str:
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        depth, ok = 0, True
        for i, ch in enumerate(s):
            depth += (ch == "(") - (ch == ")")
            if depth == 0 and i < len(s) - 1:
                ok = False
                break
        if not ok:
            break
        s = s[1:-1].strip()
    return s


def parse_bool_formula(text) -> list[tuple[str, list[str]]]:
    """
    «A AND (B OR C) AND (S43.0, S43.1) AND T11.2» → [(kind, tokens), …].
    kind: "cat" — є категорії; "code" — лише коди S/T (перемикач «коди S/T обов'язкові»);
    "req" — лише інші коди (напр., *-код G63.6) — завжди обов'язкові.
    Група «Діагноз_Z» повертається як ("cat", ["Z"]).
    """
    f = _clean(text)
    groups = []
    for conj in _split_top(f, "AND"):
        inner = _strip_parens(conj)
        toks: list[str] = []
        for item in _split_top(inner, "OR"):
            m = re.fullmatch(r"(?:код\s+)?Діагноз_(ПП|ФО|СФЗ|СП|С|Z)", _strip_parens(item))
            if m:
                toks.append(CAT_MAP[m.group(1)])
            else:
                toks += codes_in(item)
        toks = list(dict.fromkeys(toks))
        if not toks:
            continue
        if any(t in CAT_MAP.values() for t in toks):
            kind = "cat"
        elif all(t[0] in "ST" for t in toks):
            kind = "code"
        else:
            kind = "req"
        groups.append((kind, toks))
    return groups


@dataclass
class FormulaRow:
    row: int
    text: str
    groups: list


def load_formulas(path: str) -> dict[str, FormulaRow]:
    """Код → формула; для кодів у кількох рядках — рядок, де рубрика коду представлена найвужче."""
    rows = read_rows(path)
    parsed = {}
    by_code = defaultdict(list)
    row_codes = {}
    for i, r in enumerate(rows, 2):
        cs = codes_in(r[0])
        row_codes[i] = cs
        parsed[i] = FormulaRow(i, _clean(r[1]), parse_bool_formula(r[1]))
        for c in cs:
            by_code[c].append(i)
    out = {}
    for c, rr in by_code.items():
        best = min(rr, key=lambda i: sum(1 for x in row_codes[i] if x[:3] == c[:3]))
        out[c] = parsed[best]
    return out


# ------------------------------------------------------------------------------ перелік основних
def load_main_list(path: str) -> dict[str, list[str]]:
    """Код → умови використання (порожня умова = «так»)."""
    out: dict[str, list[str]] = defaultdict(list)
    for r in read_rows(path):
        cond = _clean(r[1] if len(r) > 1 else "") or "так"
        for c in codes_in(r[0]):
            if cond not in out[c]:
                out[c].append(cond)
    return dict(out)


# ------------------------------------------------------------------------------ категорії
def load_categories(path: str) -> dict[str, set[str]]:
    """Код → категорії. Файл: заголовки «Діагноз_ПП», «Діагноз_ФО» … «Діагноз_Z», під ними — коди через кому."""
    ws = load_workbook(path, read_only=True, data_only=True).worksheets[0]
    rows = [r for r in ws.iter_rows(values_only=True) if any(v not in (None, "") for v in r)]
    out: dict[str, set[str]] = defaultdict(set)
    header = [_clean(h) for h in rows[0]]
    for r in rows[1:]:
        for h, v in zip(header, r):
            m = re.fullmatch(r"Діагноз\s*_\s*(ПП|ФО|СФЗ|СП|С|Z)", h)
            if m:
                for c in codes_in(v):
                    out[c].add(CAT_MAP[m.group(1)])
    return dict(out)


# ------------------------------------------------------------------------------ пари †/*
@dataclass
class PairRow:
    row: int
    daggers: list[str]
    stars: list[str]


def load_pairs(path: str) -> list[PairRow]:
    return [PairRow(i, codes_in(r[0]), codes_in(r[1])) for i, r in enumerate(read_rows(path), 2)]


def ranges_text(codes: list[str], limit: int = 12) -> str:
    """Стисле подання переліку кодів: рубрики діапазонами (A00–B99, M47)."""
    rubs = sorted(set(c[:3] for c in codes))
    out, start, prev = [], None, None
    for r in rubs:
        if prev and r[0] == prev[0] and int(r[1:3]) == int(prev[1:3]) + 1:
            prev = r
            continue
        if start:
            out.append(start if start == prev else f"{start}–{prev}")
        start = prev = r
    if start:
        out.append(start if start == prev else f"{start}–{prev}")
    if len(rubs) == len(codes) and len(codes) <= limit:
        return ", ".join(codes) if len(codes) <= 3 else ", ".join(out)
    if len(codes) <= 4:
        return ", ".join(codes)
    txt = ", ".join(out[:limit]) + (" …" if len(out) > limit else "")
    return txt
