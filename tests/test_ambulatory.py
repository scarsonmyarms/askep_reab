"""Амбулаторна реабілітація: відповідність послугам АР1/АР2, АР3-1, АР3-2, АР4 за діагнозами
(лист НСЗУ № 8575/8-15-26 від 01.04.2026, переліки — ambulatory_services.json)."""
import pytest

from coding_rules import (FAIL, OK, PERIOD_POST, SETTING_INPATIENT, SETTING_OUTPATIENT, WARN, load_ambulatory,
                          validate)


def svc(rep):
    return {l.text.split(" (")[0]: l.level for l in rep.services if l.level != "ℹ"}


def V(d, main, comps, **kw):
    return validate(d, PERIOD_POST, main, comps, setting=SETTING_OUTPATIENT, **kw)


def test_data_file():
    amb = load_ambulatory()
    ids = [s["id"] for s in amb["services"]]
    assert ids == ["AP12", "AP3-1", "AP3-2", "AP4"]
    codes = {c for s in amb["services"] for c in s["codes"]}
    assert "H54.0" in codes and "T11.6" in codes and "Н54.0" not in codes      # кирилицю замінено латиницею


def test_inpatient_has_no_services(d):
    assert validate(d, PERIOD_POST, "I63.3", ["Z50.0", "G81.9"], setting=SETTING_INPATIENT).services == []


def test_main_in_list(d):
    s = svc(V(d, "I63.3", ["Z50.0", "G81.9"]))
    assert s["АР2"] == OK and s["АР3-1"] == OK and s["АР3-2"] == FAIL


def test_ap1_with_sr_record(d):
    s = svc(V(d, "I63.3", ["Z50.0", "G81.9"], sr_record=True))
    assert "АР1" in s and "АР2" not in s


def test_only_companion_in_list_warns(d):
    """A32.1 не в переліку АР1/АР2, але G81.9 (супутній) — є: ⚠, бо не ясно, чи достатньо супутнього."""
    s = svc(V(d, "A32.1", ["Z50.0", "G81.9"]))
    assert s["АР2"] == WARN


def test_rubric_in_list_matches_detailed(d):
    """У переліку АР3-1 — рубрика G11; G11 у довіднику збігається."""
    assert svc(V(d, "G11", ["Z50.0"]))["АР3-1"] == OK


def test_coding_summary_not_affected(d):
    r_in = validate(d, PERIOD_POST, "A32.1", ["Z50.0", "G81.9"])
    r_out = V(d, "A32.1", ["Z50.0", "G81.9"])
    assert r_in.summary == r_out.summary


@pytest.mark.real
def test_real_m17(real_nszu):
    """M17.0 (гонартроз) — у переліках АР3-1, АР3-2, АР4; для АР1/АР2 у переліку лише супутній G63.6 → ⚠."""
    s = svc(validate(real_nszu, PERIOD_POST, "M17.0", ["R26.2", "Z50.1", "G63.6"], setting=SETTING_OUTPATIENT))
    assert s["АР2"] == WARN and s["АР3-1"] == OK and s["АР3-2"] == OK and s["АР4"] == OK
