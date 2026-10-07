"""
Регресійні тести на реальному довіднику + файлах НСЗУ (лежать поруч із dod1.xlsx у tests/).
Пропускаються, якщо будь-якого з 4 файлів НСЗУ немає.
"""
import pytest

from coding_rules import FAIL, OK, PERIOD_LONG, PERIOD_POST, WARN, validate

pytestmark = pytest.mark.real


def test_counts(real_nszu):
    d = real_nszu
    assert len(d.items) == 6855                 # + Z50.4, Z50.5, Z50.7, Z50.8 з файлу категорій
    assert len(d.main_candidates(PERIOD_POST)) == 4956
    assert len(d.main_candidates(PERIOD_LONG)) == 3673


def test_specific_row_g54_2(real_nszu):
    """G54.2 є і в групі G54, і окремо — діє окремий рядок «(ФО OR СП) AND Z»."""
    assert [g.tokens for g in real_nszu.find("G54.2").groups] == [["ФО", "СП"]]
    assert [g.tokens for g in real_nszu.find("G54.0").groups] == [["ПП"], ["ФО", "СП"]]


def test_rubrics_replaced(real_nszu):
    assert real_nszu.find("G54") is None and real_nszu.find("R47") is None
    assert real_nszu.find("R47.0") is not None and real_nszu.find("M54.16") is not None


SCENARIOS = [
    (PERIOD_POST, "I63.3", ["G81.9", "R47.0", "Z50.1"], FAIL),        # G81.9 (поле 1) вимагає ПП серед супутніх
    (PERIOD_POST, "I63.3", ["R26.2", "G81.9", "Z50.1"], OK),
    (PERIOD_POST, "I63.3", ["G81.9", "R47.0"], FAIL),                 # без Z50.x
    (PERIOD_POST, "G54.2", ["R26.2", "Z50.1"], OK),
    (PERIOD_POST, "M00.01", ["G63.6", "Z50.1"], OK),                 # пара †/* і явна вимога G63.6
    (PERIOD_POST, "M00.01", ["R26.2", "Z50.1"], FAIL),               # бракує G63.6
    (PERIOD_LONG, "T92.3", ["S43.01", "T11.2", "G81.9", "Z50.1"], OK),
    (PERIOD_LONG, "T92.3", ["S43.01", "G81.9", "Z50.1"], WARN),      # T11.2 — рекомендовано (перемикач S/T)
    (PERIOD_POST, "G99.2", ["C72.0", "Z50.1"], FAIL),               # C72.0 (поле 1) вимагає ФО або С серед супутніх
    (PERIOD_POST, "G99.2", ["C72.0", "R26.2", "Z50.1"], OK),
    (PERIOD_POST, "D18.2", ["G81.9", "Z50.1"], FAIL),                # немає в переліку основних НСЗУ
    (PERIOD_POST, "A32.1", ["G81.9", "Z50.1", "I10 Гіпертензія"], FAIL),  # A32.1 — †-код, потрібен G94.0*
    (PERIOD_POST, "A32.1", ["G81.9", "G94.0", "Z50.1", "I10 Гіпертензія"], OK),
    (PERIOD_POST, "B01.0", ["K59.2", "Z47.9"], FAIL),               # випадок зі скриншоту: бракує G94.0*
    (PERIOD_POST, "B01.0", ["K59.2", "G94.0", "Z47.9"], FAIL),       # Z47.9 — СФЗ, а потрібен Z50.x
    (PERIOD_POST, "B01.0", ["K59.2", "G94.0", "Z50.1"], OK),
    (PERIOD_POST, "M17.0", ["R26.2", "Z50.1"], FAIL),               # M17.0 — †-код (G63.6*)
]


def _id(s):
    p = "post" if s[0] == PERIOD_POST else "long"
    lvl = {OK: "OK", FAIL: "FAIL", WARN: "WARN"}[s[3]]
    return f"nszu {p}: {' + '.join([s[1]] + [c.split()[0] for c in s[2]])} -> {lvl}"


@pytest.mark.parametrize("period,main,comps,level", SCENARIOS, ids=[_id(s) for s in SCENARIOS])
def test_scenarios(real_nszu, combo_log, period, main, comps, level):
    d = real_nszu
    rep = validate(d, period, main, comps)
    names = [d.find(x).name if d.find(x) else f"{x} (немає в довіднику)" for x in [main] + comps]
    lines = [f"джерела: довідник + файли НСЗУ", f"період: {period}", f"основний: {names[0]}"]
    lines += [f"супутній {i}: {n}" for i, n in enumerate(names[1:], 1)]
    lines += [f"очікувано: {level}   отримано: {rep.summary.level} {rep.summary.text}"]
    lines += [f"  причина: {l.level} {l.text}" for l in rep.all_lines() if l.level in (FAIL, WARN)]
    combo_log.append({"title": "НСЗУ: " + " + ".join([main] + comps), "lines": lines,
                      "passed": rep.summary.level == level, "report": rep.as_text()})
    assert rep.summary.level == level
