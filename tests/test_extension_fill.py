"""
Заповнення полів розширенням (extension/fill.js) на імітації сторінки Askep (tests/fixtures/askep_mock.html).
Імітація відтворює поведінку автокомпліта Vuetify 2 (затримка пошуку, меню варіантів, вибір кліком),
але не є реальною сторінкою — остаточна перевірка лише на Askep.
Потрібно: pip install playwright && python -m playwright install chromium (інакше тести пропускаються).
"""
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parent.parent
FILL = (ROOT / "extension" / "fill.js").read_text(encoding="utf-8")
MOCK = (Path(__file__).parent / "fixtures" / "askep_mock.html").as_uri()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Chromium для Playwright недоступний: {e}")
        yield b
        b.close()


@pytest.fixture
def page(browser):
    pg = browser.new_page()
    pg.goto(MOCK)
    pg.add_script_tag(content=FILL)
    yield pg
    pg.close()


def fill(page, entries, **opts):
    return page.evaluate("([e, o]) => askepFillDiagnoses(e, o)", [entries, {"timeout": 3000, **opts}])


E = lambda role, code: {"role": role, "code": code, "name": code}


def test_probe_finds_fields(page):
    r = fill(page, [], dryRun=True)
    assert [f["index"] for f in r["fields"]] == [1, 2]


def test_fills_in_order(page):
    r = fill(page, [E("Основний", "I63.3"), E("Супутній 1", "G81.9")])
    assert [x["level"] for x in r["results"]] == ["✔", "✔"]
    vals = [f["value"] for f in fill(page, [], dryRun=True)["fields"]]
    assert vals[0].startswith("I63.3") and vals[1].startswith("G81.9")


def test_no_free_field_without_autoadd(page):
    r = fill(page, [E("Основний", "I63.3"), E("Супутній 1", "G81.9"), E("Супутній 2", "R26.2")], autoAdd=False)
    assert r["results"][2]["level"] == "✖"


def test_autoadd_clicks_button(page):
    """Полів 2, діагнозів 4 — розширення двічі натискає «Додати ще один діагноз»."""
    r = fill(page, [E("Основний", "I63.3"), E("Супутній 1", "G81.9"), E("Супутній 2", "R26.2"), E("Супутній 3", "R47.1")])
    assert [x["level"] for x in r["results"]] == ["✔"] * 4
    assert [x["field"] for x in r["results"]] == [1, 2, 3, 4]
    assert page.evaluate("document.querySelectorAll('.block').length") == 4


def test_autoadd_selects_new_diagnosis_type(page):
    """Після «Додати ще один діагноз» у новому блоці вибрано «Новий діагноз», а не інший тип."""
    fill(page, [E("Основний", "I63.3"), E("Супутній 1", "G81.9"), E("Супутній 2", "R26.2")])
    types = page.evaluate("[...document.querySelectorAll('.type .v-select__selection')].map(e => e.textContent)")
    assert types == ["Новий діагноз"] * 3


def test_existing_block_without_type(page):
    """Блок уже додано вручну, але тип не вибрано (поля коду ще немає) — тип вибирається, код заповнюється."""
    page.evaluate("addBlock(3, false)")
    r = fill(page, [E("Основний", "I63.3"), E("Супутній 1", "G81.9"), E("Супутній 2", "R26.2")], autoAdd=False)
    assert [x["level"] for x in r["results"]] == ["✔"] * 3
    assert page.evaluate("document.querySelectorAll('.block').length") == 3


def test_probe_does_not_change_type(page):
    page.evaluate("addBlock(3, false)")
    fill(page, [], dryRun=True)
    assert page.evaluate("document.querySelectorAll('.type .v-select__selection').length") == 2


def test_autoadd_button_missing(page):
    page.evaluate("document.getElementById('add-btn').remove()")
    r = fill(page, [E("Основний", "I63.3"), E("Супутній 1", "G81.9"), E("Супутній 2", "R26.2")])
    assert r["results"][2]["level"] == "✖" and "не знайдено" in r["results"][2]["text"]


def test_incremental_skips_present(page):
    fill(page, [E("Основний", "I63.3"), E("Супутній 1", "G81.9")])
    page.evaluate("addBlock(3, true)")
    r = fill(page, [E("Основний", "I63.3"), E("Супутній 1", "G81.9"), E("Супутній 2", "R26.2")])
    assert [x["level"] for x in r["results"]] == ["ℹ", "ℹ", "✔"]


def test_rubric_not_matched_to_subcode(page):
    """R47 не вибирається як R47.0 — лише точний код."""
    r = fill(page, [E("Основний", "R47")])
    assert r["results"][0]["level"] == "⚠" and "оберіть вручну" in r["results"][0]["text"]


def test_not_found_code(page):
    r = fill(page, [E("Основний", "Z99.9")], timeout=1500)
    assert r["results"][0]["level"] == "⚠"


def test_dynamic_id_not_required(page):
    """Поля знаходяться за підписом, навіть якщо id змінився."""
    page.evaluate("document.querySelectorAll('input[placeholder]').forEach((el, i) => el.id = 'input-' + (900 + i))")
    assert len(fill(page, [], dryRun=True)["fields"]) == 2
