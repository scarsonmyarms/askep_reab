"""Поради щодо вибору основного діагнозу (розділ ІІ Правил) і заміна основного."""
from coding_rules import INFO, PERIOD_LONG, PERIOD_POST, WARN, plan_slots, swap_main, validate

Z = "Z50.0"


def adv(d, main, comps, period=PERIOD_POST):
    return validate(d, period, main, comps).advice


def test_etiology_post_acute_warns_with_swap(d):
    a = adv(d, "G81.9", ["I63.3", Z])
    assert len(a) == 1 and a[0]["kind"] == "etiology" and a[0]["level"] == WARN and a[0]["swap_code"] == "I63.3"


def test_etiology_long_term_soft_hint_without_swap(d):
    a = adv(d, "G81.9", ["I63.3", Z], PERIOD_LONG)
    assert a[0]["level"] == INFO and a[0]["swap"] is None


def test_etiology_only_acute_causes(d):
    """G93.1 + I46.0 — правильне кодування за CR_2_3 (I46.0 не гостра етіологія з переліку) — без поради."""
    assert adv(d, "G93.1", ["I46.0", Z]) == []


def test_no_advice_when_main_is_etiology(d):
    assert adv(d, "I63.3", ["G81.9", Z]) == []


def test_pain_with_structural_pathology(d):
    a = adv(d, "M54.5", ["G81.9", Z, "M51.1"])
    assert len(a) == 1 and a[0]["kind"] == "pain" and a[0]["swap_code"] == "M51.1"


def test_pain_without_structure_no_advice(d):
    assert adv(d, "M54.5", ["G81.9", Z]) == []


def test_typed_codes_ignored(d):
    assert adv(d, "G81.9", ["I63.9 введено вручну", Z]) == []


def test_advice_line_in_report(d):
    r = validate(d, PERIOD_POST, "G81.9", ["I63.3", Z])
    assert any(l.level == WARN and "Причину встановлено" in l.text for l in r.main)


def test_swap_moves_old_main_into_matching_slot(d):
    i63, g81 = d.find("I63.3").name, d.find("G81.9").name
    main, vals = swap_main(d, g81, {"m0": i63, "m1": d.find(Z).name}, i63)
    assert main == i63
    slots = plan_slots(d, d.find(main), vals)
    assert g81 in [s.value for s in slots if s.role == "main"]      # G81.9 — у полі «ФО або С» нового основного
    assert i63 not in vals.values()
