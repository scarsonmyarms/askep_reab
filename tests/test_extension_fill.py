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


# ------------------------------------------------------------------ вкладки та шкала Бартел
def test_opens_diagnoses_tab_first(page):
    """Сторінка відкрита на «Діагностичних звітах» — розширення спершу переходить на «Діагнози»."""
    r = fill(page, [E("Основний", "I63.3")])
    assert r["results"][0]["level"] == "✔"
    assert page.evaluate("document.querySelector('[data-panel=p-diag]').getAttribute('aria-selected')") == "true"


def test_barthel_flow(page):
    r = fill(page, [E("Основний", "I63.3"), E("Супутній 1", "G81.9")], barthel=True)
    steps = {x["role"]: (x["level"], x["text"]) for x in r["results"]}
    assert steps["Діагностичний звіт"][0] == "✔" and "96037-00" in steps["Діагностичний звіт"][1]
    assert steps["Спостереження: тип"] == ("✔", "вибрано: Загальні спостереження (LOINC)")
    assert page.evaluate("document.getElementById('input-1261').getAttribute('aria-checked')") == "true"
    assert steps["Спостереження: категорія"][0] == "✔"
    assert steps["Спостереження: вид"][0] == "✔" and "Barthel_Extended" in steps["Спостереження: вид"][1]
    assert steps["Спостереження: посилання"][0] == "✔"
    assert "06.10.2026" in steps["Спостереження: посилання"][1]          # найновіший звіт 96037-00
    sel = page.evaluate("[...document.querySelectorAll('#p-rep .v-select__selection, #p-obs .v-select__selection')].map(e => e.textContent)")
    assert sel[0].startswith("96037-00") and sel[1] == "Шкали оцінки, опитування"
    assert sel[2].startswith("Barthel_Extended") and sel[3].startswith("(96037-00)")
    assert page.evaluate("document.querySelector('#p-rep .v-select__selection') !== null")
    # виконавця (інше поле зі списком) не зачеплено
    assert page.evaluate("document.querySelectorAll('#p-rep .v-select__selection').length") == 1


def test_barthel_second_run_skips(page):
    fill(page, [E("Основний", "I63.3")], barthel=True)
    r = fill(page, [E("Основний", "I63.3")], barthel=True)
    levels = {x["role"]: x["level"] for x in r["results"]}
    assert levels["Діагностичний звіт"] == "ℹ" and levels["Спостереження: категорія"] == "ℹ"
    assert levels["Спостереження: тип"] == "ℹ"
    assert levels["Спостереження: вид"] == "ℹ" and levels["Спостереження: посилання"] == "ℹ"


def test_barthel_off_by_default(page):
    r = fill(page, [E("Основний", "I63.3")])
    assert [x["role"] for x in r["results"]] == ["Основний"]


def test_radio_missing(page):
    """Немає перемикача «Загальні спостереження (LOINC)» — далі не йдемо, повідомляємо."""
    page.evaluate("document.querySelector('label[for=input-1261]').textContent = 'Інша назва'")
    r = fill(page, [E("Основний", "I63.3")], barthel=True)
    last = r["results"][-1]
    assert last["role"] == "Спостереження: тип" and last["level"] == "✖"


def test_reference_found_by_heading(page):
    """Посилання шукається лише в полі під заголовком «Посилання на діагностичний звіт»; інші поля не відкриваються."""
    page.evaluate("""() => { window.__opened = []; document.addEventListener('click', e => {
        const i = e.target.closest('.v-input'); if (i) window.__opened.push(i.parentElement.textContent.trim().slice(0, 40)); }, true); }""")
    r = fill(page, [E("Основний", "I63.3")], barthel=True)
    assert r["results"][-1]["level"] == "✔"
    assert not any("Виконавець спостереження" in x for x in page.evaluate("window.__opened"))
    assert page.evaluate("document.querySelector('.col-6 .v-select__selection').textContent").startswith("(96037-00)")


def test_reference_heading_missing(page):
    page.evaluate("""() => { const t = () => { const h = [...document.querySelectorAll('.v-subheader')]
        .find(x => x.textContent.trim() === 'Посилання на діагностичний звіт');
        if (h) h.textContent = 'Інший заголовок'; else setTimeout(t, 100); }; t(); }""")
    r = fill(page, [E("Основний", "I63.3")], barthel=True)
    assert r["results"][-1]["level"] == "✖" and "не знайдено" in r["results"][-1]["text"]


# ------------------------------------------------------------------ «Заключення лікаря»
TEXT = "Пацієнт після ішемічного інсульту, геміпарез справа. Рекомендовано продовжити реабілітацію."


def test_conclusion_in_barthel_flow(page):
    r = fill(page, [E("Основний", "I63.3")], barthel=True, conclusion=TEXT)
    roles = [x["role"] for x in r["results"]]
    assert roles.index("Заключення лікаря") == roles.index("Діагностичний звіт") + 1        # перед спостереженнями
    assert roles.index("Заключення лікаря") < roles.index("Спостереження: тип")
    assert page.evaluate("document.getElementById('input-1135').value") == TEXT
    assert page.evaluate("document.querySelector('#p-rep .v-counter').textContent").startswith(str(len(TEXT)))


def test_conclusion_without_barthel(page):
    r = fill(page, [E("Основний", "I63.3")], conclusion=TEXT)
    assert [x["role"] for x in r["results"]] == ["Основний", "Заключення лікаря"]
    assert r["results"][-1]["level"] == "✔"


def test_conclusion_not_overwritten(page):
    page.evaluate("document.getElementById('input-1135').value = 'Текст, підтягнутий з ЕМК'")
    r = fill(page, [E("Основний", "I63.3")], conclusion=TEXT)
    assert r["results"][-1]["level"] == "⚠"
    assert page.evaluate("document.getElementById('input-1135').value") == "Текст, підтягнутий з ЕМК"


def test_conclusion_empty_reminder(page):
    r = fill(page, [E("Основний", "I63.3")], barthel=True)
    c = [x for x in r["results"] if x["role"] == "Заключення лікаря"][0]
    assert c["level"] == "⚠" and "обов'язкове" in c["text"]
