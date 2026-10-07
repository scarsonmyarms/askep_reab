"""Перевірка кодування: статуси основного, груп формул, супутніх, пар †/*, несумісних поєднань, підсумок.
У кожному випадку обов'язковий код Діагноз_Z (Z50.x), тому в «правильних» наборах є Z50.0."""
import pytest

from coding_rules import FAIL, INFO, OK, PERIOD_LONG, PERIOD_POST, WARN, validate

Z = "Z50.0"   # код Діагноз_Z (Z50.x)


def V(d, main, comps=(), period=PERIOD_POST, st=False):
    return validate(d, period, main, list(comps), st)


def levels(lines):
    return [l.level for l in lines]


def has(lines, level, fragment):
    return any(l.level == level and fragment in l.text for l in lines)


def comp(rep, i):
    return rep.companions[i][1]


class TestMain:
    def test_not_selected(self, d):
        assert V(d, "").summary.level == FAIL

    def test_unknown(self, d):
        assert V(d, "X99 Невідомий").summary.level == FAIL

    def test_cannot_be_main(self, d):
        r = V(d, "R26.2", ["I46.0", Z])
        assert has(r.main, FAIL, "Не може бути основним")
        assert r.summary.text == "Основний діагноз некоректний"

    def test_wrong_period(self, d):
        r = V(d, "S06.0", ["G81.9", Z], period=PERIOD_LONG)
        assert has(r.main, FAIL, "у періоді") and r.summary.level == FAIL

    def test_right_period(self, d):
        assert V(d, "T90.5", ["G81.9", "S06.0", Z], period=PERIOD_LONG).summary.level == OK

    def test_conditional_warns(self, d):
        r = V(d, "M54.1", [Z, "G81.9"])
        assert has(r.main, WARN, "Умовно") and r.summary.level == WARN


class TestZRequired:
    """Діагноз_Z (коди Z50.x) обов'язковий у кожному випадку; СФЗ (Z74.x, Z99.x …) — окрема, необов'язкова категорія."""

    def test_missing_z_fails(self, d):
        r = V(d, "A32.1", ["G11"])
        assert has(r.main_groups, FAIL, "Діагноз_Z") and r.summary.level == FAIL

    def test_z50_code_ok(self, d):
        r = V(d, "A32.1", ["G11", "Z50.0"])
        assert has(r.main_groups, OK, "Діагноз_Z") and r.summary.level == OK

    def test_sfz_does_not_replace_z(self, d):
        r = V(d, "A32.1", ["G11", "Z74.1"])
        assert has(r.main_groups, FAIL, "Діагноз_Z")

    def test_sfz_is_optional_info(self, d):
        r = V(d, "A32.1", ["G11", Z, "Z74.1"])
        assert has(comp(r, 2), INFO, "СФЗ") and r.summary.level == OK

    def test_z_companion_fits_formula(self, d):
        assert has(comp(V(d, "A32.1", ["G11", Z]), 1), OK, "Відповідає")


class TestMainFormula:
    def test_met_by_companion(self, d):
        r = V(d, "A32.1", [Z, "G81.9"])
        assert levels(r.main_groups) == [OK, OK] and r.summary.level == OK

    def test_missing(self, d):
        assert has(V(d, "A32.1", [Z]).main_groups, FAIL, "бракує: Діагноз_ФО")

    def test_self_covered_no_companion_needed(self, d):
        """G93.7 має ФО → формула «плюс ФО» виконана самим діагнозом; потрібен лише СФЗ."""
        r = V(d, "G93.7", [Z])
        assert has(r.main_groups, OK, "виконано самим діагнозом") and r.summary.level == OK

    def test_g93_1(self, d):
        """G93.1 (ФО): «ПП» + «ФО або СП» (закрито самим ФО) + СФЗ."""
        r = V(d, "G93.1", ["I46.0", Z])
        assert levels(r.main_groups) == [OK, OK, OK]
        assert has(r.main_groups, OK, "самим діагнозом (ФО)")

    def test_g93_1_missing_pp(self, d):
        assert has(V(d, "G93.1", ["R26.2", Z]).main_groups, FAIL, "бракує: Діагноз_ПП")

    def test_ta_abo_is_or(self, d):
        """I63.3: «ФО та/або С» = ФО АБО С — досить одного (приклад 1 з Правил + СФЗ)."""
        assert V(d, "I63.3", [Z, "G81.9", "R47"]).summary.level == OK
        assert V(d, "I63.3", [Z, "Z96.6"]).summary.level == OK

    def test_abo_one_is_enough(self, d):
        r = V(d, "M45.0", ["R26.2", Z])          # ПП — сам; «ФО або СП або С» — R26.2
        assert FAIL not in levels(r.main_groups)

    @pytest.mark.parametrize("st,level", [(False, WARN), (True, FAIL)])
    def test_code_group_switch(self, d, st, level):
        r = V(d, "T90.5", [Z, "G81.9"], period=PERIOD_LONG, st=st)
        assert has(r.main_groups, level, "S06") and r.summary.level == level


class TestCompanions:
    def test_fits_main(self, d):
        assert has(comp(V(d, "A32.1", ["G81.9", Z]), 0), OK, "Відповідає формулі основного")

    def test_duplicate(self, d):
        r = V(d, "A32.1", ["G81.9", "G81.9", Z])
        assert has(comp(r, 1), FAIL, "Повтор") and r.summary.level == FAIL

    def test_same_as_main(self, d):
        r = V(d, "A32.1", ["A32.1 Лістеріозний менінгіт та менінгоенцефаліт", Z])
        assert has(comp(r, 0), FAIL, "Збігається з основним")

    def test_not_in_formula_warns(self, d):
        r = V(d, "A32.1", [Z, "G81.9", "Z96.6"])
        assert has(comp(r, 2), WARN, "Не передбачено") and r.summary.level == WARN

    def test_comorbidity_outside_directory(self, d):
        r = V(d, "A32.1", [Z, "G81.9", "I10 Гіпертензія"])
        assert has(comp(r, 2), INFO, "Немає в довіднику") and r.summary.level == OK

    def test_empty_strings_ignored(self, d):
        assert len(V(d, "A32.1", ["G81.9", "", "  ", Z]).companions) == 2


class TestCompanion1Formula:
    def test_own_formula_self_covered(self, d):
        """G11 («ПП або ФО або СП») закриває свою формулу сам."""
        r = V(d, "A32.1", ["G11", Z])
        assert has(comp(r, 0), OK, "самим діагнозом") and r.summary.level == OK

    def test_main_not_counted(self, d):
        """Умови супутнього 1 основний не закриває: G81.9 вимагає ПП, основний A32.1 (ПП) не враховується."""
        r = V(d, "A32.1", ["G81.9", Z])
        assert has(comp(r, 0), FAIL, "Його група 1: бракує: Діагноз_ПП") and r.summary.level == FAIL

    def test_met_by_other_companion(self, d):
        """ПП для G81.9 закриває інший супутній (I46.0)."""
        r = V(d, "A32.1", ["G81.9", "I46.0", Z])
        assert has(comp(r, 0), OK, "Його група 1: Діагноз_ПП — виконано") and r.summary.level == OK

    def test_own_formula_not_met(self, d):
        """Z74.1 у полі 1 вимагає ПП; основний G93.1 не враховується, інші супутні ПП не мають."""
        r = V(d, "G93.1", ["Z74.1", Z])
        assert has(comp(r, 0), FAIL, "Його група 1: бракує: Діагноз_ПП")

    def test_companion2_formula_not_applied(self, d):
        r = V(d, "A32.1", ["G11", "Z74.1", Z])          # Z74.1 у полі 2 вимагає ПП — не перевіряється
        assert not any("Його група" in l.text for l in comp(r, 1))
        assert r.summary.level == OK


class TestPairs:
    def test_dagger_without_star_fails(self, d):
        r = V(d, "A17.8", ["G81.9", Z])
        assert has(r.main, FAIL, "G63.0") and r.summary.level == FAIL

    def test_dagger_with_star_ok(self, d):
        assert V(d, "A17.8", [Z, "G63.0"]).summary.level == OK

    def test_star_main_needs_range_dagger(self, d):
        assert has(V(d, "C72.0", ["G55.0", Z]).companions[0][1], OK, "Парний код")

    def test_manual(self, d):
        assert has(V(d, "G01", ["G81.9", Z]).main, WARN, "перевірте вручну")

    def test_recommended(self, d):
        r = V(d, "M51.1", [Z, "G81.9"])
        assert has(r.main, WARN, "Рекомендовано") and r.summary.level == WARN

    def test_companion_pair_checked(self, d):
        assert has(comp(V(d, "C72.0", ["G81.9", "A17.8", Z]), 1), FAIL, "парний код")


class TestExclusions:
    def test_fail(self, d):
        r = V(d, "M51.1", ["G55.1", "M54.1", Z])
        assert has(r.exclusions, FAIL, "M54.1 + M51.1") and r.summary.level == FAIL

    def test_none(self, d):
        assert not V(d, "M54.1", ["G55.1", Z]).exclusions

    def test_arthritis_combined(self, d):
        assert has(V(d, "M05.0", ["G81.9", "M13.8", Z]).exclusions, FAIL, "M05 + M13")


class TestReport:
    def test_as_text_sections(self, d):
        t = V(d, "A32.1", ["G81.9", Z]).as_text()
        for s in ("ОСНОВНИЙ ДІАГНОЗ", "ФОРМУЛА ОСНОВНОГО", "СУПУТНІ", "НЕСУМІСНІ ПОЄДНАННЯ", "ПІДСУМОК"):
            assert s in t
