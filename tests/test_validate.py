"""Перевірка кодування: статуси основного, груп формул, супутніх, пар †/*, несумісних поєднань, підсумок."""
import pytest

from coding_rules import FAIL, INFO, OK, PERIOD_LONG, PERIOD_POST, WARN, validate


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
        r = V(d, "")
        assert r.summary.level == FAIL

    def test_unknown(self, d):
        assert V(d, "X99 Невідомий").summary.level == FAIL

    def test_cannot_be_main(self, d):
        r = V(d, "R26.2", ["I46.0"])
        assert has(r.main, FAIL, "Не може бути основним")
        assert r.summary.text == "Основний діагноз некоректний"

    def test_wrong_period(self, d):
        r = V(d, "S06.0", ["G81.9"], period=PERIOD_LONG)
        assert has(r.main, FAIL, "у періоді")
        assert r.summary.level == FAIL

    def test_right_period(self, d):
        assert V(d, "T90.5", ["G81.9", "S06.0"], period=PERIOD_LONG).summary.level == OK

    def test_conditional_warns(self, d):
        r = V(d, "M54.1", ["G81.9"])
        assert has(r.main, WARN, "Умовно")
        assert r.summary.level == WARN


class TestMainFormula:
    def test_met_by_companion(self, d):
        r = V(d, "A32.1", ["G81.9"])
        assert levels(r.main_groups) == [OK] and r.summary.level == OK

    def test_missing(self, d):
        r = V(d, "A32.1")
        assert has(r.main_groups, FAIL, "бракує: Діагноз_ФО")

    def test_self_covered_no_companion_needed(self, d):
        """G93.7 має ФО → формула «плюс ФО» виконана самим діагнозом."""
        r = V(d, "G93.7")
        assert has(r.main_groups, OK, "виконано самим діагнозом")
        assert r.summary.level == OK

    def test_g93_1_three_groups(self, d):
        r = V(d, "G93.1", ["I46.0", "R26.2"])
        assert levels(r.main_groups) == [OK, OK, OK]
        assert has(r.main_groups, OK, "самим діагнозом (ФО)")

    def test_g93_1_missing_sp(self, d):
        r = V(d, "G93.1", ["I46.0"])
        assert has(r.main_groups, FAIL, "бракує: Діагноз_СП")

    def test_ta_abo_requires_both(self, d):
        """I63.3: «ФО та/або С» = ФО і С обидва."""
        assert has(V(d, "I63.3", ["G81.9"]).main_groups, FAIL, "Діагноз_С")
        assert V(d, "I63.3", ["G81.9", "Z96.6"]).summary.level == OK

    def test_abo_one_is_enough(self, d):
        r = V(d, "M45.0", ["G81.9", "Z96.6"])          # ПП — сам; ФО — G81.9; «СП або С» — Z96.6
        assert FAIL not in levels(r.main_groups)

    @pytest.mark.parametrize("st,level", [(False, WARN), (True, FAIL)])
    def test_code_group_switch(self, d, st, level):
        r = V(d, "T90.5", ["G81.9"], period=PERIOD_LONG, st=st)
        assert has(r.main_groups, level, "S06")
        assert r.summary.level == level


class TestCompanions:
    def test_fits_main(self, d):
        assert has(comp(V(d, "A32.1", ["G81.9"]), 0), OK, "Відповідає формулі основного")

    def test_duplicate(self, d):
        r = V(d, "A32.1", ["G81.9", "G81.9"])
        assert has(comp(r, 1), FAIL, "Повтор") and r.summary.level == FAIL

    def test_same_as_main(self, d):
        r = V(d, "A32.1", ["A32.1 Лістеріозний менінгіт та менінгоенцефаліт"])
        assert has(comp(r, 0), FAIL, "Збігається з основним")

    def test_not_in_formula_warns(self, d):
        r = V(d, "A32.1", ["G81.9", "Z96.6"])
        assert has(comp(r, 1), WARN, "Не передбачено")

    def test_sfz_info(self, d):
        r = V(d, "A32.1", ["G81.9", "Z50.0"])
        assert has(comp(r, 1), INFO, "СФЗ") and r.summary.level == OK

    def test_comorbidity_outside_directory(self, d):
        r = V(d, "A32.1", ["G81.9", "I10 Гіпертензія"])
        assert has(comp(r, 1), INFO, "Немає в довіднику") and r.summary.level == OK

    def test_empty_strings_ignored(self, d):
        assert len(V(d, "A32.1", ["G81.9", "", "  "]).companions) == 1


class TestCompanion1Formula:
    def test_own_formula_self_covered_and_missing(self, d):
        """Сценарій зі скриншоту: G11 закриває ПП і ФО сам, бракує СП."""
        r = V(d, "A32.1", ["G11"])
        c = comp(r, 0)
        assert sum(has([l], OK, "самим діагнозом") for l in c) == 2
        assert has(c, FAIL, "бракує: Діагноз_СП") and r.summary.level == FAIL

    def test_own_formula_met_by_other(self, d):
        r = V(d, "A32.1", ["G11", "R26.2"])
        assert r.summary.level == OK

    def test_own_formula_met_by_main(self, d):
        """G81.9 вимагає ПП — закриває основний A32.1."""
        assert has(comp(V(d, "A32.1", ["G81.9"]), 0), OK, "Його група 1: Діагноз_ПП — виконано")

    def test_companion2_formula_not_applied(self, d):
        r = V(d, "A32.1", ["G81.9", "G11"])          # G11 у полі 2 — його СП не вимагається
        assert not any("Його група" in l.text for l in comp(r, 1))
        assert r.summary.level == OK


class TestPairs:
    def test_dagger_without_star_fails(self, d):
        r = V(d, "A17.8", ["G81.9"])
        assert has(r.main, FAIL, "G63.0") and r.summary.level == FAIL

    def test_dagger_with_star_ok(self, d):
        assert V(d, "A17.8", ["G63.0"]).summary.level == OK

    def test_star_main_needs_range_dagger(self, d):
        assert has(V(d, "C72.0", ["G55.0"]).companions[0][1], OK, "Парний код")

    def test_manual(self, d):
        assert has(V(d, "G01", ["G81.9"]).main, WARN, "перевірте вручну")

    def test_recommended(self, d):
        r = V(d, "M51.1", ["G81.9"])
        assert has(r.main, WARN, "Рекомендовано") and r.summary.level == WARN

    def test_companion_pair_checked(self, d):
        r = V(d, "C72.0", ["G81.9", "A17.8"])
        assert has(comp(r, 1), FAIL, "парний код")


class TestExclusions:
    def test_fail(self, d):
        r = V(d, "M51.1", ["G55.1", "M54.1"])
        assert has(r.exclusions, FAIL, "M54.1 + M51.1") and r.summary.level == FAIL

    def test_warn(self, d):
        r = V(d, "M54.1", ["G55.1"])      # немає несумісностей G54 → тут лише умовний основний
        assert not r.exclusions

    def test_arthritis_combined(self, d):
        r = V(d, "M05.0", ["G81.9", "M13.8"])
        assert has(r.exclusions, FAIL, "M05 + M13")


class TestReport:
    def test_as_text_sections(self, d):
        t = V(d, "A32.1", ["G81.9"]).as_text()
        for s in ("ОСНОВНИЙ ДІАГНОЗ", "ФОРМУЛА ОСНОВНОГО", "СУПУТНІ", "НЕСУМІСНІ ПОЄДНАННЯ", "ПІДСУМОК"):
            assert s in t
