"""
Регресійний тест: 66 справжніх випадків стаціонарної реабілітації (пакет 53) з вердиктом НСЗУ
(розшифровка за вересень 2026, знеособлено — лише коди діагнозів і результат; див. nszu_cases_2026_09.json).

Запуск окремо від основного набору:   pytest -m regression -rxX
Потрібні реальний довідник і файли НСЗУ в tests/ (як для tests/test_real_nszu.py).

Що перевіряється:
  * випадок, який НСЗУ ЗАРАХУВАЛА, — програма не повинна показувати ✖ (помилку кодування);
  * випадок, де НСЗУ знайшла «Для діагнозу X не виконано вимогу…», — програма має показати ✖ щодо X.
Відомі розбіжності — правила, у яких програма свідомо відрізняється від перевірки НСЗУ і щодо яких
рішення ще не ухвалено, — позначаються як xfail з поясненням (не «ламають» набір, але видно, скільки їх):
  K1 — формулу супутнього 1 основний діагноз не закриває (НСЗУ основний враховує);
  K2 — кожен †-код вимагає *-код (НСЗУ зараховує без нього);
  K3 — несумісність M54.1 + M51.1 (CR_3_5) як помилка (НСЗУ зараховує);
  K4 — формули додаткових діагнозів, крім супутнього 1, не перевіряються (НСЗУ перевіряє всі);
  K5 — *-код вимагає †-код (НСЗУ зарахувала G55.1* без M50–M51†).
Будь-яка інша розбіжність — справжня регресія, тест падає.
Період реабілітації в розшифровці не вказано, тож береться кращий результат із двох періодів.
"""
import json
from collections import Counter
from pathlib import Path

import pytest

from coding_rules import FAIL, PERIOD_LONG, PERIOD_POST, validate

pytestmark = pytest.mark.regression

DATA = json.loads(Path(__file__).with_name("nszu_cases_2026_09.json").read_text(encoding="utf-8"))
CASES = DATA["cases"]
RESULTS: Counter = Counter()

K = {
    "K1": "формулу супутнього 1 основний діагноз не закриває (НСЗУ основний враховує)",
    "K2": "кожен †-код вимагає *-код (НСЗУ зараховує без нього)",
    "K3": "M54.1 + M51.1 (CR_3_5) як помилка (НСЗУ зараховує)",
    "K4": "формули додаткових діагнозів, крім супутнього 1, не перевіряються (НСЗУ перевіряє всі)",
    "K5": "*-код вимагає †-код (НСЗУ зараховує без нього)",
}


def pair_kind(text):
    """«Додайте парний код †/*: … *» — бракує *-коду (K2); «… †» — бракує †-коду (K5)."""
    t = text.rstrip()
    return "K2" if t.endswith("*") else "K5" if t.endswith("†") else "REAL"


def best_report(d, case):
    """Кращий результат із двох періодів (період у розшифровці не вказано)."""
    reps = [validate(d, p, case["main"], case["additional"]) for p in (PERIOD_POST, PERIOD_LONG)]
    order = {"✔": 0, "⚠": 1, "✖": 2}
    return min(reps, key=lambda r: order[r.summary.level])


def classify_failures(d, case, rep):
    """Кожен наш ✖ → код відомої розбіжності (K1–K3) або 'REAL' (справжня розбіжність)."""
    out = []
    main = d.find(case["main"])
    comps = [d.find(c) or d.adhoc(c) for c in case["additional"]]
    c1 = comps[0] if comps else None
    for l in rep.main + rep.main_groups:
        if l.level == FAIL:
            out.append((pair_kind(l.text) if "парний код" in l.text else "REAL", l.text))
    for l in rep.exclusions:
        if l.level == FAIL:
            out.append(("K3" if l.text.startswith("M54.1 + ") else "REAL", l.text))
    for idx, (_, lines) in enumerate(rep.companions):
        for l in lines:
            if l.level != FAIL:
                continue
            if "парний код" in l.text:
                out.append((pair_kind(l.text), l.text))
            elif l.text.startswith("Його група") and c1 is not None and main is not None:
                # вимогу закрив би основний діагноз → K1
                k = int(l.text.split(":")[0].split()[-1]) - 1
                g = c1.cgroups[k]
                out.append(("K1" if main.matches(g.ts) else "REAL", l.text))
            else:
                out.append(("REAL", l.text))
    return out


def _id(c):
    return f"case{c['case']:02d}-row{c['source_row']}-{c['main']}-{'OK' if c['nszu_accepted'] else 'REJ'}"


@pytest.mark.parametrize("case", CASES, ids=[_id(c) for c in CASES])
def test_case(real_nszu, case):
    d = real_nszu
    rep = best_report(d, case)
    if case["nszu_accepted"]:
        if rep.summary.level != FAIL:
            RESULTS["збіг"] += 1
            return
        found = classify_failures(d, case, rep)
        real = [t for k, t in found if k == "REAL"]
        if real:
            RESULTS["справжня розбіжність"] += 1
            pytest.fail(f"НСЗУ зарахувала, а програма показує ✖: {real}")
        kinds = sorted({k for k, _ in found})
        for k in kinds:
            RESULTS[k] += 1
        pytest.xfail("відома розбіжність: " + "; ".join(f"{k} — {K[k]}" for k in kinds))
    # НСЗУ відхилила через формулу діагнозу X
    for err in case["nszu_diagnosis_errors"]:
        code = err.split("Для діагнозу ")[1].split()[0]
        ours = [l.text for l in rep.all_lines() if l.level == FAIL and code in l.text]
        ours += [l.text for name, ls in rep.companions if name.startswith(code + " ")
                 for l in ls if l.level == FAIL]
        if ours:
            RESULTS["збіг"] += 1
            continue
        if code != case["main"] and case["additional"] and case["additional"][0] != code:
            RESULTS["K4"] += 1
            pytest.xfail(f"відома розбіжність: K4 — {K['K4']} (НСЗУ: «{err}»)")
        RESULTS["справжня розбіжність"] += 1
        pytest.fail(f"НСЗУ: «{err}», а програма цього не знаходить")


def test_zz_summary(real_nszu, combo_log):
    """Зведення по всіх випадках — у розділі «Комбінації діагнозів…» наприкінці запуску."""
    total = len(CASES)
    lines = [f"випадків: {total} (зараховано НСЗУ: {sum(c['nszu_accepted'] for c in CASES)})",
             f"збіг з НСЗУ: {RESULTS['збіг']}",
             *[f"{k}: {RESULTS[k]} — {K[k]}" for k in K if RESULTS[k]],
             f"справжні розбіжності: {RESULTS['справжня розбіжність']}"]
    combo_log.append({"title": "РЕГРЕСІЯ: вердикти НСЗУ (вересень 2026)", "lines": lines,
                      "passed": RESULTS["справжня розбіжність"] == 0})
    assert RESULTS["справжня розбіжність"] == 0
