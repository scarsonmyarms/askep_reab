"""Завантаження довідника та властивості діагнозів."""
import pytest

from coding_rules import PERIOD_LONG, PERIOD_POST


def test_dedup(d):
    assert sum(1 for x in d.items if x.code == "G81.9") == 1


def test_nbsp_cleaned(d):
    x = d.find("A06.6")
    assert x.name == "A06.6 Амебний абсцес головного мозку"


@pytest.mark.parametrize("q", ["G81.9", "G81.9 Геміплегія, неуточнена", "  G81.9 Геміплегія, неуточнена "])
def test_find_by_code_or_name(d, q):
    assert d.find(q).code == "G81.9"


def test_find_unknown(d):
    assert d.find("I10 Гіпертензія") is None


def test_code_and_mark_from_name(d):
    x = d.find("G55.1")
    assert x.code == "G55.1" and x.mark == "*"
    assert d.find("A17.8").mark == "†"


def test_categories(d):
    assert d.find("G93.7").cats == {"ПП", "ФО"}
    assert d.find("G93.7").cats_text == "ПП, ФО"
    assert d.find("Z50.0").cats == {"СФЗ"}


class TestMainRules:
    def test_can_be_main(self, d):
        assert d.find("G81.9").can_be_main
        assert not d.find("R26.2").can_be_main

    def test_period(self, d):
        s06, t90 = d.find("S06.0"), d.find("T90.5")
        assert s06.main_in_period(PERIOD_POST) and not s06.main_in_period(PERIOD_LONG)
        assert t90.main_in_period(PERIOD_LONG) and not t90.main_in_period(PERIOD_POST)

    def test_conditional(self, d):
        assert d.find("M54.1").conditional
        assert not d.find("G81.9").conditional

    def test_main_candidates(self, d):
        post = {x.code for x in d.main_candidates(PERIOD_POST)}
        long = {x.code for x in d.main_candidates(PERIOD_LONG)}
        assert "S06.0" in post and "S06.0" not in long
        assert "T90.5" in long and "T90.5" not in post
        assert "R26.2" not in post | long


class TestMatches:
    def test_by_category(self, d):
        assert d.find("G81.9").matches(["ФО"])
        assert not d.find("G81.9").matches(["СП"])

    @pytest.mark.parametrize("tok", ["S06", "S06.0"])
    def test_by_code_prefix(self, d, tok):
        assert d.find("S06.0").matches([tok])

    def test_star_code_prefix(self, d):
        assert d.find("G63.0").matches(["G63.0"])


class TestPairs:
    """Подвійне кодування †/* (розділ III Правил)."""

    def test_dagger_needs_star(self, d):
        x = d.find("A17.8")
        assert x.pair_flag == 1 and x.pair_tokens == ["G63.0"]

    def test_star_needs_dagger(self, d):
        x = d.find("G63.0")
        assert x.pair_flag == 1 and "A17.8" in x.pair_tokens

    def test_star_range(self, d):
        x = d.find("G55.0")
        assert x.pair_flag == 1 and "C72" in x.pair_tokens and "D48" in x.pair_tokens

    def test_star_without_reference_manual(self, d):
        assert d.find("G01").pair_flag == 2

    def test_unmarked_with_star_ref_recommended(self, d):
        x = d.find("M51.1")
        assert x.pair_flag == 3 and x.pair_tokens == ["G55.1"]

    def test_no_pair(self, d):
        assert d.find("G81.9").pair_flag == 0
