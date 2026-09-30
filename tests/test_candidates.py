"""Формування випадаючих списків супутніх діагнозів."""
from coding_rules import PERIOD_POST


def codes(lst):
    return {x.code for x in lst}


def cats_of(lst):
    return set().union(*(x.cats for x in lst)) if lst else set()


def test_no_main_empty(d):
    assert d.companion_candidates(None, 0, []) == []


def test_slot1_by_main_formula(d):
    c = d.companion_candidates(d.find("A32.1"), 0, [])
    assert c and all("ФО" in x.cats for x in c)


def test_main_excluded(d):
    main = d.find("G93.7")
    assert main.name not in {x.name for x in d.companion_candidates(main, 0, [])}


def test_self_covered_group_not_in_list(d):
    """G93.1 сам має ФО → у списку поля 1 лише ПП і СП, без «чистих» ФО."""
    c = d.companion_candidates(d.find("G93.1"), 0, [])
    assert all(x.cats & {"ПП", "СП"} for x in c)
    assert "G81.9" not in codes(c)


def test_all_self_covered_fallback(d):
    """G93.7 (ПП, ФО, формула «плюс ФО»): вимог немає, але список ФО лишається для необов'язкових."""
    c = d.companion_candidates(d.find("G93.7"), 0, [])
    assert c and all("ФО" in x.cats for x in c)


def test_slot2_only_unmet(d):
    """Сценарій зі скриншоту: A32.1 + G11 → у полі 2 лише СП."""
    main, g11 = d.find("A32.1"), d.find("G11")
    c = d.companion_candidates(main, 1, [g11])
    assert c and all("СП" in x.cats for x in c)


def test_slot2_after_all_met_shows_non_self_covered(d):
    main, g11, sp = d.find("A32.1"), d.find("G11"), d.find("R26.2")
    c3 = d.companion_candidates(main, 2, [g11, sp])
    assert cats_of(c3) >= {"ФО", "СП"}
    assert "R26.2" not in codes(c3)          # уже обраний раніше — виключений


def test_slot_own_choice_stays_in_its_list(d):
    """Обраний у полі 2 діагноз не «вибиває» сам себе зі свого списку."""
    main, g11, sp = d.find("A32.1"), d.find("G11"), d.find("R26.2")
    assert "R26.2" in codes(d.companion_candidates(main, 1, [g11, sp]))


def test_slot2_uses_companion1_formula(d):
    """G93.1 + I46.0 (ПП у полі 1): для поля 2 лишається лише СП."""
    main, i46 = d.find("G93.1"), d.find("I46.0")
    c = d.companion_candidates(main, 1, [i46])
    assert c and all("СП" in x.cats for x in c)


def test_later_slots_ignore_companion2_formula(d):
    """Формули супутніх 2+ не застосовуються: СП з формули G11 (поле 2) не з'являється в полі 3."""
    main, g81, g11 = d.find("A32.1"), d.find("G81.9"), d.find("G11")
    c3 = d.companion_candidates(main, 2, [g81, g11])
    assert "R26.2" not in codes(c3)          # R26.2 — лише СП
    assert "R47" in codes(c3)                # ФО — з формули основного


def test_code_group_in_list(d):
    c = d.companion_candidates(d.find("T90.5"), 0, [])
    assert "S06.0" in codes(c)


def test_pair_code_in_list(d):
    """Парний *-код основного потрапляє в список, навіть якщо формула його не вимагає."""
    assert "G63.0" in codes(d.companion_candidates(d.find("A17.8"), 0, []))


def test_pair_of_previous_companion_in_next_list(d):
    main, a17 = d.find("C72.0"), d.find("A17.8")
    assert "G63.0" in codes(d.companion_candidates(main, 1, [a17]))


def test_broad_list_contains_narrow(d):
    main, g11 = d.find("A32.1"), d.find("G11")
    narrow = codes(d.companion_candidates(main, 1, [g11]))
    broad = codes(d.companion_candidates(main, 1, [g11], narrow=False))
    assert narrow <= broad and len(broad) > len(narrow)
