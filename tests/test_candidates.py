"""Формування випадаючих списків супутніх діагнозів."""


def codes(lst):
    return {x.code for x in lst}


def cats_of(lst):
    return set().union(*(x.cats for x in lst)) if lst else set()


def test_no_main_empty(d):
    assert d.companion_candidates(None, 0, []) == []


def test_slot1_by_main_formula_and_sfz(d):
    """A32.1 (формула «ФО») — у полі 1 ФО та обов'язковий Z (Z50.x)."""
    c = d.companion_candidates(d.find("A32.1"), 0, [])
    assert c and all(x.cats & {"ФО", "Z"} for x in c)
    assert {"G81.9", "Z50.0"} <= codes(c)


def test_main_excluded(d):
    main = d.find("G93.7")
    assert main.name not in {x.name for x in d.companion_candidates(main, 0, [])}


def test_own_category_does_not_close_formula(d):
    """G93.1 сам є ФО, але власну вимогу «ФО або СП» не закриває — ФО/СП у списку поля 1."""
    c = d.companion_candidates(d.find("G93.1"), 0, [])
    assert "G81.9" in codes(c) and "R26.2" in codes(c)


def test_main_formula_category_in_list(d):
    """G93.7 (ПП, ФО; формула «ФО»): ФО обов'язковий серед супутніх, хоча основний сам ФО."""
    c = d.companion_candidates(d.find("G93.7"), 0, [])
    assert cats_of(c) >= {"ФО", "Z"}


def test_slot2_only_unmet(d):
    """A32.1 + G81.9 (формула «ПП») + I46.0 (ПП): усе закрито, крім Z → у полі 3 лише Z."""
    main, g81, i46 = d.find("A32.1"), d.find("G81.9"), d.find("I46.0")
    c = d.companion_candidates(main, 2, [g81, i46])
    assert c and all("Z" in x.cats for x in c)


def test_companion1_own_category_not_counted(d):
    """A32.1 + G11 (ПП, ФО; формула «ПП або ФО або СП»): G11 сам себе не закриває → у полі 2 ПП/ФО/СП і Z."""
    c = d.companion_candidates(d.find("A32.1"), 1, [d.find("G11")])
    assert "R26.2" in codes(c) and "Z50.0" in codes(c)


def test_slot3_after_all_met(d):
    main, g81, i46, z = d.find("A32.1"), d.find("G81.9"), d.find("I46.0"), d.find("Z50.0")
    c4 = d.companion_candidates(main, 3, [g81, i46, z])
    assert "ФО" in cats_of(c4) and "Z50.0" not in codes(c4)


def test_slot_own_choice_stays_in_its_list(d):
    main, g81, i46, z = d.find("A32.1"), d.find("G81.9"), d.find("I46.0"), d.find("Z50.0")
    assert "Z50.0" in codes(d.companion_candidates(main, 2, [g81, i46, z]))


def test_slot2_uses_companion1_formula(d):
    """A32.1 + G81.9: формула G81.9 («ПП») основним не закривається → у полі 2 ПП і Z (Z50.x)."""
    main, g81 = d.find("A32.1"), d.find("G81.9")
    c = d.companion_candidates(main, 1, [g81])
    assert c and all(x.cats & {"ПП", "Z"} for x in c) and cats_of(c) >= {"ПП", "Z"}


def test_later_slots_ignore_companion2_formula(d):
    """Формула G11 у полі 2 не застосовується: R26.2 (лише СП) не з'являється в полі 3."""
    main, g81, g11 = d.find("A32.1"), d.find("G81.9"), d.find("G11")
    c3 = d.companion_candidates(main, 2, [g81, g11])
    assert "R26.2" not in codes(c3)
    assert "Z50.0" in codes(c3)


def test_code_group_in_list(d):
    c = d.companion_candidates(d.find("T90.5"), 0, [])
    assert "S06.0" in codes(c)


def test_pair_code_in_list(d):
    assert "G63.0" in codes(d.companion_candidates(d.find("A17.8"), 0, []))


def test_pair_of_previous_companion_in_next_list(d):
    main, a17 = d.find("C72.0"), d.find("A17.8")
    assert "G63.0" in codes(d.companion_candidates(main, 1, [a17]))


def test_broad_list_contains_narrow(d):
    main, g81, i46 = d.find("A32.1"), d.find("G81.9"), d.find("I46.0")
    narrow = codes(d.companion_candidates(main, 2, [g81, i46]))
    broad = codes(d.companion_candidates(main, 2, [g81, i46], narrow=False))
    assert narrow <= broad and len(broad) > len(narrow)
