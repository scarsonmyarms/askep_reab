"""Розбір формул кодування (стовпець O) і діапазонів кодів."""
import pytest

from coding_rules import _expand_any, _expand_st, parse_formula

FO, PP, SP, C_ = '"Діагноз_ФО"', '"Діагноз_ПП"', '"Діагноз_СП"', '"Діагноз_С"'


def kinds_tokens(formula):
    groups, star = parse_formula(formula)
    return [(g.kind, g.tokens) for g in groups], star


class TestGroups:
    def test_single_category(self):
        assert kinds_tokens(f"плюс код(и) {FO}") == ([("cat", ["ФО"])], False)

    def test_two_plus_are_two_groups(self):
        g, _ = kinds_tokens(f"плюс код {PP} плюс код(и) {FO}")
        assert g == [("cat", ["ПП"]), ("cat", ["ФО"])]

    def test_ta_abo_is_or(self):
        """«та/або» = АБО (як у нових файлах: «Діагноз_ПП AND (Діагноз_ФО OR Діагноз_СП)»)."""
        g, _ = kinds_tokens(f"плюс код {PP} плюс код(и) {FO} та/або код(и) {SP}")
        assert g == [("cat", ["ПП"]), ("cat", ["ФО", "СП"])]

    def test_abo_is_or(self):
        g, _ = kinds_tokens(f"плюс код {PP} та/або код(и) {FO} та/або код(и) {SP} або код(и) {C_}")
        assert g == [("cat", ["ПП", "ФО", "СП", "С"])]

    def test_ta_kod_splits(self):
        g, _ = kinds_tokens(f"плюс код {PP} гострого стану та код(и) {FO}")
        assert g == [("cat", ["ПП"]), ("cat", ["ФО"])]

    @pytest.mark.parametrize("text,cat", [
        ('"Діагноз_С"', "С"), ('"Діагноз_СП"', "СП"), ('"Діагноз_СФЗ"', "СФЗ"),
        ('"Діагноз _ПП"', "ПП"),               # пробіл перед підкресленням (зустрічається в таблиці)
    ])
    def test_category_names_not_confused(self, text, cat):
        g, _ = kinds_tokens(f"плюс код {text}")
        assert g == [("cat", [cat])]

    def test_star_code_flag(self):
        g, star = kinds_tokens(f"плюс код(и) {FO} плюс *-код")
        assert star is True and g == [("cat", ["ФО"])]

    @pytest.mark.parametrize("formula", ["", None, "   "])
    def test_empty(self, formula):
        assert kinds_tokens(formula) == ([], False)


class TestCodeGroups:
    def test_code_group_kind(self):
        g, _ = kinds_tokens(f"плюс код S06 або T90.5 плюс код(и) {FO}")
        assert g == [("code", ["S06", "T90.5"]), ("cat", ["ФО"])]

    def test_ranges_and_lists(self):
        """Кома — АБО, «та» в переліку кодів — окрема обов'язкова група (як у нових файлах для T90.8)."""
        g, _ = kinds_tokens(f"плюс код S03.-, S07-S08 та S09.0-S09.2 плюс код(и) {FO}")
        assert g[:2] == [("code", ["S03", "S07", "S08"]), ("code", ["S09.0", "S09.1", "S09.2"])]

    def test_range_with_trailing_dash_and_newline(self):
        g, _ = kinds_tokens("плюс код S14.0-S14.1-, S24.2-\nS24.4, T09.0- та T11.2.-")
        assert g == [("code", ["S14.0", "S14.1", "S24.2", "S24.3", "S24.4", "T09.0"]), ("code", ["T11.2"])]

    def test_no_space_after_kod(self):
        g, _ = kinds_tokens(f"плюс кодS76.-, S86.- та T13.5 плюс код(и) {FO}")
        assert g[:2] == [("code", ["S76", "S86"]), ("code", ["T13.5"])]

    def test_t92_3_like_new_file(self):
        """T92.3 у новому файлі: (S43 | S53 | S63) AND T11.2 AND Діагноз_ФО."""
        g, _ = kinds_tokens(f"плюс код S43.-, S53.-, S63.- та T11.2.- плюс код(и) {FO}")
        assert g == [("code", ["S43", "S53", "S63"]), ("code", ["T11.2"]), ("cat", ["ФО"])]


class TestExpand:
    def test_st_three_char(self):
        assert _expand_st("T00", "T03") == ["T00", "T01", "T02", "T03"]

    def test_st_decimal(self):
        assert _expand_st("S14.2", "S14.4") == ["S14.2", "S14.3", "S14.4"]

    def test_single(self):
        assert _expand_st("S06", "") == ["S06"]

    def test_across_letters(self):
        r = _expand_any("C00", "D48")
        assert r[0] == "C00" and r[-1] == "D48" and "C99" in r and "D00" in r and "D49" not in r
        assert len(r) == 100 + 49
