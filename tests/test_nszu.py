"""
Джерела НСЗУ: перелік основних, формули (основний/додатковий) і пари †/* замість довідника.
Синтетичні файли створюються в тимчасовій папці поруч із тестовим довідником.
"""
import pytest
from openpyxl import Workbook

from coding_rules import FAIL, OK, PERIOD_LONG, PERIOD_POST, TokenSet, code_matches, Directory, validate
from conftest import FO, MINI_ROWS, PP, make_xlsx
import nszu_sources as nszu

DIR_EXTRA = [
    ("G54 Ураження нервових корінців та сплетінь", "ПП,ФО", "так", f"плюс код {PP} плюс код(и) {FO}"),
    ("G54.2 Ураження шийних корінців", "ФО", "так", f"плюс код(и) {FO}"),
    ("M00.0 Стафілококовий артрит і поліартрит", "ПП", "так", f"плюс код(и) {FO}"),
    ("G63.6* Поліневропатія при інших кістково-м'язових ураженнях", "ФО", "ні", f"плюс код {PP}"),
]


def _xlsx(path, header, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(list(r))
    wb.save(path)


@pytest.fixture(scope="module")
def nz(tmp_path_factory) -> Directory:
    folder = tmp_path_factory.mktemp("nszu")
    make_xlsx(folder / "dod1.xlsx", MINI_ROWS + DIR_EXTRA)
    _xlsx(folder / "Перелік_основний_діагнозів_.xlsx", ["Код основного діагнозу", "Умова використання"], [
        ("G54.0, G54.2, M54.10, M54.16, A32.1, G11.1, C16.0, A17.8, M00.01, M05.0, G93.7", None),
        ("S06.0, I63.3", "протягом післягострого реабілітаційного періоду"),
        ("I69.3", "в довготривалому періоді"),
        ("R47.0", "якщо відсутнє інше домінуюче функціональне обмеження"),
    ])
    _xlsx(folder / "Співвідношення_коду_основного_діагнозу_та_формули_кодування_додаткових_діагнозів.xlsx",
          ["Код основного діагнозу", "Формула"], [
              ("G54.2", "(Діагноз_ФО OR Діагноз_СП) AND Діагноз_Z"),
              ("G54.0, G54.1, G54.2, G54.3", "Діагноз_ПП AND (Діагноз_ФО OR Діагноз_СП) AND Діагноз_Z"),
              ("A32.1, G11.1, G93.7", "Діагноз_ФО AND Діагноз_Z"),
              ("M54.1", "Діагноз_ПП AND Діагноз_ФО AND Діагноз_Z"),
              ("I63.3", "(Діагноз_ФО OR Діагноз_С) AND Діагноз_Z"),
              ("T92.3", "(S43.0, S53.1) AND T11.2 AND Діагноз_ФО AND Діагноз_Z"),
              ("M00.01", "Діагноз_ФО AND G63.6 AND Діагноз_Z"),
          ])
    _xlsx(folder / "Співвідношення_коду_додаткового_діагнозу_та_формули_кодування__діагнозів.xlsx",
          ["Код додаткового діагозу", "Формула"], [
              ("G81.9", "Діагноз_ПП OR Діагноз_ФО"),
              ("R26.2", "Діагноз_ПП"),
              ("Z74.1, Z50.0", "Діагноз_ПП"),
              ("G63.6, G63.0", "Діагноз_ПП OR Діагноз_ФО"),
          ])
    _xlsx(folder / "Перелік_пар_діагнозів_хрестик_та_зірочка.xlsx", ["Код діагноз хрестик", "Код діагноз зірочка"], [
        ("A17.8", "G63.0"),
        ("M00.01, M05.0", "G63.6"),
    ])
    return Directory(str(folder / "dod1.xlsx"))


Z = "Z50.0"


def test_files_detected(nz):
    f = nz.nszu
    assert f.main_list and f.formulas_main and f.formulas_add and f.pairs
    assert len(nz.sources) == 5


def test_without_nszu_files_old_mode(mini_dir):
    assert mini_dir.nszu is None


class TestMainList:
    def test_main_from_list_not_column_n(self, nz):
        assert not nz.find("G81.9").can_be_main            # у довіднику «так», у переліку — немає
        assert nz.find("G54.2").can_be_main

    def test_period(self, nz):
        assert nz.find("S06.0").main_in_period(PERIOD_POST) and not nz.find("S06.0").main_in_period(PERIOD_LONG)
        assert nz.find("I69.3").main_in_period(PERIOD_LONG) and not nz.find("I69.3").main_in_period(PERIOD_POST)

    def test_conditional(self, nz):
        assert nz.find("R47.0").conditional

    def test_main_candidates(self, nz):
        post = {x.code for x in nz.main_candidates(PERIOD_POST)}
        assert {"S06.0", "G54.2", "C16.0"} <= post and "I69.3" not in post and "G81.9" not in post


class TestItems:
    def test_rubric_replaced_by_detailed_codes(self, nz):
        assert nz.find("G54") is None and nz.find("M54.1") is None
        x = nz.find("M54.16")
        assert x.name == "M54.16 Радикулопатія (уточнення коду M54.1)" and x.cats == {"ПП"}

    def test_code_without_directory(self, nz):
        x = nz.find("C16.0")
        assert x.name == "C16.0 (назви немає в довіднику)" and x.cats == set()

    def test_dir_only_kept(self, nz):
        assert nz.find("G81.0") is None or nz.find("G81.0").source == "довідник"
        assert nz.find("I46.0").source == "довідник"


class TestFormulas:
    def test_specific_row_wins(self, nz):
        """G54.2 є і в групі G54, і окремо — діє окремий рядок."""
        assert [g.tokens for g in nz.find("G54.2").groups] == [["ФО", "СП"]]
        assert [g.tokens for g in nz.find("G54.0").groups] == [["ПП"], ["ФО", "СП"]]

    def test_rubric_formula_for_detailed_code(self, nz):
        """M54.16 немає у формулах — береться формула рубрики M54.1."""
        assert [g.tokens for g in nz.find("M54.16").groups] == [["ПП"], ["ФО"]]

    def test_z_is_case_group(self, nz):
        assert all("Z" not in g.tokens for g in nz.find("A32.1").groups)
        r = validate(nz, PERIOD_POST, "A32.1", ["G81.9"])
        assert r.summary.level == FAIL and any("Діагноз_Z" in l.text for l in r.main_groups)
        assert validate(nz, PERIOD_POST, "A32.1", ["G81.9", Z]).summary.level == OK

    def test_comp_formula_from_additional_file(self, nz):
        """G81.9 у ролі супутнього: «ПП або ФО» (файл додаткових), а не «ПП» з довідника."""
        g81 = nz.find("G81.9")
        assert [g.tokens for g in g81.cgroups] == [["ПП", "ФО"]]
        r = validate(nz, PERIOD_POST, "G54.2", ["G81.9", Z])
        assert any("самим діагнозом" in l.text for l in r.companions[0][1])

    def test_code_groups_kinds(self, nz):
        kinds = [(g.kind, g.tokens) for g in nz.find("T92.3").groups]
        assert kinds == [("code", ["S43.0", "S53.1"]), ("code", ["T11.2"]), ("cat", ["ФО"])]

    def test_required_star_code_not_switchable(self, nz):
        """M00.01: «AND G63.6» — обов'язково навіть з перемикачем S/T «рекомендовані»."""
        r = validate(nz, PERIOD_POST, "M00.01", ["G81.9", Z], st_required=False)
        assert any(l.level == FAIL and "G63.6" in l.text for l in r.main_groups)
        assert validate(nz, PERIOD_POST, "M00.01", ["G63.6", Z]).summary.level == OK


class TestPairs:
    def test_star_requires_dagger_from_list(self, nz):
        x = nz.find("G63.0")
        assert x.pair_flag == 1 and x.pair_tokens == ["A17.8"]

    def test_name_pairs_ignored(self, nz):
        """M51.1 у назві згадує G55.1, але в переліку пар цієї пари немає."""
        assert nz.find("M51.1").pair_flag == 0

    def test_any_dagger_requires_star(self, nz):
        """Будь-який †-код з переліку пар обов'язково потребує *-коду (навіть без позначки «†» у довіднику)."""
        m05 = nz.find("M05.0")
        assert m05.pair_flag == 1 and m05.pair_tokens == ["G63.6"]
        assert "G63.6" in {x.code for x in nz.companion_candidates(m05, 0, [])}
        assert validate(nz, PERIOD_POST, "M05.0", ["G81.9", Z]).summary.level == FAIL
        assert validate(nz, PERIOD_POST, "M05.0", ["G63.6", Z]).summary.level == OK

    def test_marked_dagger_requires_star(self, nz):
        assert nz.find("A17.8").pair_flag == 1


class TestMatching:
    @pytest.mark.parametrize("code,tok,ok", [
        ("R47", "R47.0", True), ("R47.0", "R47", True), ("S06.20", "S06", True),
        ("M54.16", "M54.1", True), ("M54.1", "M54.16", True), ("G81.9", "G81.90", True),
        ("G81.9", "G81.1", False), ("M54.16", "M54.2", False),
    ])
    def test_code_matches(self, code, tok, ok):
        assert code_matches(code, TokenSet([tok])) is ok


class TestParsing:
    def test_bool_formula(self):
        g = nszu.parse_bool_formula("Діагноз_ПП AND (Діагноз_ФО OR код Діагноз_СП) AND (S43.0, S53.1) AND G63.6 AND Діагноз_Z")
        assert g == [("cat", ["ПП"]), ("cat", ["ФО", "СП"]), ("code", ["S43.0", "S53.1"]), ("req", ["G63.6"]), ("cat", ["Z"])]

    def test_top_level_or(self):
        assert nszu.parse_bool_formula("Діагноз_ПП OR Діагноз_ФО OR Діагноз_СП") == [("cat", ["ПП", "ФО", "СП"])]

    def test_cyrillic_code(self):
        assert nszu.codes_in("М76, Н54.0") == ["M76", "H54.0"]


class TestDirectoryOnlyNamesAndCategories:
    """З довідника беруться лише назви й категорії I–M; стовпці N, O і позначки †/* у назвах не діють."""

    def test_column_o_not_used(self, nz):
        """I46.0: у довіднику «плюс ФО», у файлах НСЗУ формули немає — вимог немає."""
        x = nz.find("I46.0")
        assert x.groups == [] and x.cgroups == [] and x.formula == ""

    def test_main_formula_only_from_nszu(self, nz):
        """G81.9: у довіднику «плюс ПП»; у файлі основних немає, у файлі додаткових — «ПП OR ФО»."""
        x = nz.find("G81.9")
        assert x.groups == [] and [g.tokens for g in x.cgroups] == [["ПП", "ФО"]]

    def test_name_marks_not_used_for_pairs(self, nz):
        """G01* без пари в переліку пар — більше не «перевірте вручну»."""
        assert nz.find("G01").pair_flag == 0

    def test_categories_from_directory(self, nz):
        assert nz.find("G93.7").cats == {"ПП", "ФО"}
