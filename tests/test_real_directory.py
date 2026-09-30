"""Регресійні тести на реальному довіднику (Додаток). Запуск: pytest --xlsx=шлях або REHAB_XLSX=шлях."""
import pytest

from coding_rules import FAIL, OK, PERIOD_LONG, PERIOD_POST, validate

pytestmark = pytest.mark.real


def test_counts(real_dir):
    assert len(real_dir.items) == 1623
    assert len(real_dir.main_candidates(PERIOD_POST)) == 1383
    assert len(real_dir.main_candidates(PERIOD_LONG)) == 803


def test_every_formula_parsed(real_dir):
    """Кожна непорожня формула дає хоча б одну групу або *-код."""
    bad = [x.name for x in real_dir.items
           if x.formula.strip() and not x.groups and "*-код" not in x.formula]
    assert bad == []


def test_screenshot_scenario(real_dir, combo_log):
    """A32.1 + G11: поле 1 — 268 (ФО), поле 2 — лише СП (93)."""
    d = real_dir
    main, g11 = d.find("A32.1"), d.find("G11")
    n1 = len(d.companion_candidates(main, 0, []))
    c2 = d.companion_candidates(main, 1, [g11])
    only_sp = all("СП" in x.cats for x in c2)
    combo_log.append({
        "title": f"Списки: {main.name} + {g11.name}",
        "lines": [f"поле 1: {n1} у списку (очікувано 268)",
                  f"поле 2: {len(c2)} у списку (очікувано 93), лише СП: {'так' if only_sp else 'ні'}"],
        "passed": n1 == 268 and len(c2) == 93 and only_sp,
    })
    assert n1 == 268
    assert len(c2) == 93 and only_sp


SCENARIOS = [
    (PERIOD_POST, "G93.7", [], OK),
    (PERIOD_POST, "G93.1", ["I46.0", "R26.2"], OK),
    (PERIOD_POST, "A48.0", ["G81.9"], FAIL),
    (PERIOD_POST, "M54.1", ["M51.1", "R26.2"], FAIL),
    (PERIOD_LONG, "S06.21", ["G81.9"], FAIL),
    # приклад з розділу III Правил: за правилом «та/або» = «та» G63.6* (супутній 1) вимагає ще СП
    (PERIOD_POST, "M00.0", ["G63.6"], FAIL),
    (PERIOD_POST, "M00.0", ["G63.6", "R26.2"], OK),
]


def _id(s):
    period, main, comps, level = s
    p = "post" if period == PERIOD_POST else "long"          # латиницею: pytest екранує кирилицю в назвах тестів
    return f"{p}: {' + '.join([main] + comps)} -> {'OK' if level == OK else 'FAIL'}"


@pytest.mark.parametrize("period,main,comps,level", SCENARIOS, ids=[_id(s) for s in SCENARIOS])
def test_scenarios(real_dir, combo_log, period, main, comps, level):
    rep = validate(real_dir, period, main, comps)
    names = [real_dir.find(x).name if real_dir.find(x) else f"{x} (немає в довіднику)" for x in [main] + comps]
    lines = [f"період: {period}", f"основний: {names[0]}"]
    lines += [f"супутній {i}: {n}" for i, n in enumerate(names[1:], 1)] or ["супутні: —"]
    lines += [f"очікувано: {level}   отримано: {rep.summary.level} {rep.summary.text}"]
    problems = [f"{l.level} {l.text}" for l in rep.all_lines() if l.level in (FAIL, "⚠")]
    lines += [f"  причина: {p}" for p in problems]
    combo_log.append({"title": " + ".join([main] + comps), "lines": lines,
                      "passed": rep.summary.level == level, "report": rep.as_text()})
    assert rep.summary.level == level