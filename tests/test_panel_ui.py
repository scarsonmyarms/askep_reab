"""
Панель «Кодування» на сторінці (extension/panel.js) — на імітації сторінки Askep (tests/fixtures/askep_mock.html)
з тестовим довідником. Скрипти вставляються так само, як це робить background.js:
directory.js → logic.js → fill.js → panel.js. Потрібно: pip install playwright && python -m playwright install chromium.
"""
from pathlib import Path

import pytest

from export_json import export

sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "extension"
MOCK = (Path(__file__).parent / "fixtures" / "askep_mock.html").as_uri()


@pytest.fixture(scope="module")
def directory_js(tmp_path_factory):
    from conftest import make_xlsx
    folder = tmp_path_factory.mktemp("panel")
    xlsx = make_xlsx(folder / "mini.xlsx")
    out = folder / "directory.js"
    export(str(xlsx), str(out), nszu_files=None)
    return out.read_text(encoding="utf-8")


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
def page(browser, directory_js):
    pg = browser.new_page(viewport={"width": 1280, "height": 1000})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(MOCK)
    for src in (directory_js, (EXT / "logic.js").read_text(encoding="utf-8"),
                (EXT / "fill.js").read_text(encoding="utf-8"), (EXT / "panel.js").read_text(encoding="utf-8")):
        pg.add_script_tag(content=src)
    pg.wait_for_function("() => window.__askepCoding && !window.__askepCoding.shadow.querySelector('.sheet').hidden")
    yield pg
    assert errors == []
    pg.close()


# ------------------------------------------------------------------ помічники (усе — всередині Shadow DOM)
JS_SET = """([sel, v]) => { const s = window.__askepCoding.shadow; const el = s.querySelector(sel);
  el.value = v; el.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
  el.dispatchEvent(new Event('change', {bubbles: true, composed: true})); }"""


def opt(page, dl, code):
    return page.evaluate("""([dl, c]) => [...window.__askepCoding.shadow.querySelectorAll('#' + dl + ' option')]
        .map(o => o.value).find(v => v.startsWith(c + ' '))""", [dl, code])


def set_main(page, code):
    page.evaluate(JS_SET, ["#ac-main", opt(page, "ac-dl-main", code)])


def set_slot(page, i, code):
    page.evaluate(JS_SET, [f"#ac-slot-{i}", opt(page, f"ac-dl-{i}", code) or code])


def text(page, sel):
    return page.evaluate("(sel) => { const e = window.__askepCoding.shadow.querySelector(sel); return e ? e.textContent : null; }", sel)


def click(page, label, prefix=False):
    page.evaluate("""([t, p]) => [...window.__askepCoding.shadow.querySelectorAll('button')]
        .find(b => p ? b.textContent.trim().startsWith(t) : b.textContent.trim() === t).click()""", [label, prefix])


def slots(page):
    return page.evaluate("""() => [...window.__askepCoding.shadow.querySelectorAll('ol.slots > li')]
        .map(li => [li.querySelector('label').textContent, li.querySelector('.role').textContent, li.dataset.tone,
                    li.querySelector('input').value])""")


# ------------------------------------------------------------------ тести
def test_opens_with_layout(page):
    assert text(page, "h2") == "Askep Помічник"
    assert page.evaluate("window.__askepCoding.shadow.querySelector('.launcher').hidden") is True
    assert "діагноз" in text(page, "footer")
    assert page.evaluate("[...window.__askepCoding.shadow.querySelectorAll('.tab')].map(t => t.textContent)") == ["Кодування"]


def test_role_slots_and_tones(page):
    set_main(page, "A32.1")
    rows = slots(page)
    assert [r[0] for r in rows] == ["Супутній 1", "Супутній 2", "Супутній 3"]
    assert rows[0][1] == "Діагноз_ФО" and rows[0][2] == "stopped"          # обов'язкове поле порожнє — червона смуга
    assert rows[2][1] == "необов'язково" and rows[2][2] == "neutral"
    set_slot(page, 0, "G11")
    assert slots(page)[0][2] == "active"


def test_etiology_advice_and_swap(page):
    """G81.9 (ФО) основним, I63.3 серед супутніх → ⚠ і кнопка «Зробити I63.3 основним»."""
    set_main(page, "G81.9")
    set_slot(page, 0, "I63.3")
    assert "Причину встановлено" in text(page, ".problem.warn h3")
    click(page, "Зробити I63.3 основним")
    assert page.evaluate("window.__askepCoding.shadow.querySelector('#ac-main').value").startswith("I63.3")
    assert any(r[3].startswith("G81.9") for r in slots(page))                 # колишній основний — серед супутніх


def test_advice_dismiss(page):
    set_main(page, "G81.9")
    set_slot(page, 0, "I63.3")
    click(page, "Залишити")
    assert text(page, ".problem.warn h3") in (None, "") or "Причину встановлено" not in (text(page, ".problem.warn h3") or "")


def test_pain_advice(page):
    set_main(page, "M54.5")
    set_slot(page, 0, "G81.9")
    set_slot(page, 1, "Z50.0")
    set_slot(page, 2, "M51.1")
    assert "Біль основним" in text(page, ".problem.warn h3")


def test_confirm_and_cancel(page):
    set_main(page, "A32.1")
    click(page, "Заповнити на сторінці")
    assert text(page, ".confirm h3") == "Заповнити форму в Askep?"
    assert "Так, заповнити попри помилки" in text(page, ".confirm")             # бракує ФО і Z
    click(page, "Скасувати")
    assert text(page, ".confirm") is None and text(page, "#ac-main") is not None


def test_fill_from_panel(page):
    set_main(page, "I63.3")
    set_slot(page, 0, "R26.2")
    set_slot(page, 1, "Z50.0")
    click(page, "Заповнити на сторінці")
    click(page, "Так, заповнити", prefix=True)
    page.wait_for_function("() => window.__askepCoding.shadow.querySelector('.view') && "
                           "![...window.__askepCoding.shadow.querySelectorAll('ol.steps li')].some(l => l.dataset.state === 'active')",
                           timeout=60000)
    steps = page.evaluate("""() => [...window.__askepCoding.shadow.querySelectorAll('ol.steps li')]
        .map(l => [l.querySelector('.label').textContent, l.dataset.state])""")
    assert steps[0] == ["Основний I63.3", "done"]
    assert page.evaluate("[...document.querySelectorAll('#p-diag .v-autocomplete .v-select__selection')].map(e => e.textContent)")[0].startswith("I63.3")
    click(page, "Повернутися до кодування")
    assert text(page, "#ac-main") is not None


def test_escape_closes_and_launcher_reopens(page):
    page.evaluate("window.__askepCoding.shadow.querySelector('.sheet').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
    assert page.evaluate("window.__askepCoding.shadow.querySelector('.sheet').hidden") is True
    page.evaluate("window.__askepCoding.shadow.querySelector('.launcher').click()")
    assert page.evaluate("window.__askepCoding.shadow.querySelector('.sheet').hidden") is False


def test_panel_does_not_affect_page_field_search(page):
    """Поля панелі в Shadow DOM не потрапляють у пошук полів сторінки."""
    r = page.evaluate("() => askepFillDiagnoses([], {dryRun: true})")
    assert len(r["fields"]) == 2
