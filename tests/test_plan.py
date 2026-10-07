"""План полів супутніх за ролями: формула основного → пари †/* → формула супутнього 1 → необов'язкові."""
import pytest

from coding_rules import PERIOD_POST, plan_slots, slot_candidates, slot_fits, validate


def plan(d, main, **values):
    return plan_slots(d, d.find(main), {k.replace("_", ":"): (d.find(v).name if d.find(v) else v)
                                         for k, v in values.items()})


def roles(sl):
    return [(s.key, s.role) for s in sl]


def test_no_main(d):
    assert plan_slots(d, None, {}) == []


def test_main_formula_slots_and_sfz(d):
    """A32.1: формула «ФО» + обов'язковий Діагноз_Z → два поля за формулою основного + необов'язкове."""
    sl = plan(d, "A32.1")
    assert roles(sl) == [("m0", "main"), ("m1", "main"), ("f0", "free")]
    assert all("ФО" in x.cats for x in slot_candidates(d, d.find("A32.1"), sl, 0))
    assert all("Z" in x.cats for x in slot_candidates(d, d.find("A32.1"), sl, 1))


def test_self_covered_groups_have_no_slot(d):
    """G93.1 (ФО): «ПП» + «ФО або СП» (закриває сам) + Z → поля лише для ПП і Z."""
    sl = plan(d, "G93.1")
    assert [s.label.split(": ", 1)[1] for s in sl if s.role == "main"] == \
        ["Діагноз_ПП", "Діагноз_Z (обов'язковий у кожному випадку)"]


def test_pair_slot_for_main(d):
    sl = plan(d, "A17.8")
    pair = [s for s in sl if s.role == "pair"]
    assert len(pair) == 1 and pair[0].key == "p:main"
    assert [x.code for x in slot_candidates(d, d.find("A17.8"), sl, sl.index(pair[0]))] == ["G63.0"]


def test_pair_slot_disappears_when_pair_chosen_elsewhere(d):
    """Пару вже вказано в необов'язковому полі — окреме поле пари не потрібне."""
    sl = plan(d, "A17.8", f0="G63.0")
    assert not [s for s in sl if s.role == "pair"]


def test_comp1_slot(d):
    """A32.1 + G81.9 (формула «ПП», основний не враховується) → поле за формулою супутнього 1."""
    sl = plan(d, "A32.1", m0="G81.9", m1="Z50.0")
    assert [s.role for s in sl] == ["main", "main", "comp1", "free"]
    assert "G81.9" in sl[2].label and "Діагноз_ПП" in sl[2].label


def test_comp1_slot_not_needed_when_self_covered(d):
    sl = plan(d, "A32.1", m0="G11", m1="Z50.0")
    assert "comp1" not in [s.role for s in sl]


def test_comp1_slot_kept_when_filled(d):
    """Поле з уже введеним значенням не зникає, навіть якщо вимога закрита іншим полем."""
    sl = plan(d, "A32.1", m0="G81.9", m1="Z50.0", c0="I46.0", f0="M05.0")
    assert "c0" in [s.key for s in sl]


def test_values_kept_by_key(d):
    sl = plan(d, "A32.1", m0="G81.9", m1="Z50.0", c0="I46.0")
    assert [s.value.split()[0] for s in sl if s.value] == ["G81.9", "Z50.0", "I46.0"]


def test_slot_fits(d):
    sl = plan(d, "A32.1", m0="Z96.6")          # Z96.6 (С) у полі «ФО»
    assert slot_fits(sl[0]) is False
    assert slot_fits(plan(d, "A32.1", m0="G81.9")[0]) is True


def test_free_slots_grow(d):
    sl = plan(d, "A32.1", f0="I10 Гіпертензія")
    assert [s.key for s in sl if s.role == "free"] == ["f0", "f1"]


def test_candidates_exclude_taken(d):
    sl = plan(d, "A32.1", m0="G81.9")
    assert "G81.9" not in {x.code for x in slot_candidates(d, d.find("A32.1"), sl, len(sl) - 1)}


def test_validate_follows_plan_order(d):
    """Супутній 1 — перше поле плану, навіть коли воно порожнє."""
    sl = plan(d, "A32.1", m1="Z50.0", f0="G81.9")
    rep = validate(d, PERIOD_POST, "A32.1", [s.value for s in sl])
    assert not any("Його група" in l.text for _, ls in rep.companions for l in ls)


@pytest.mark.real
def test_real_b01_0(real_nszu):
    """B01.0 → ФО, Z (Z50.x), пара G94.0; формулу K59.2 (ПП) закриває G94.0."""
    d = real_nszu
    sl = plan(d, "B01.0", m0="K59.2", m1="Z50.1")
    assert roles(sl) == [("m0", "main"), ("m1", "main"), ("p:main", "pair"), ("f0", "free")]
    sl = plan(d, "B01.0", m0="K59.2", m1="Z50.1", p_main="G94.0")
    assert validate(d, PERIOD_POST, "B01.0", [s.value for s in sl]).summary.level == "✔"


@pytest.mark.real
def test_real_i63_3(real_nszu):
    """I63.3 + G81.9 → поле «за формулою супутнього 1: ПП»."""
    sl = plan(real_nszu, "I63.3", m0="G81.9", m1="Z50.1")
    assert [s.role for s in sl] == ["main", "main", "comp1", "free"]
