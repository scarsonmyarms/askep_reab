"""Димовий тест графічного інтерфейсу (пропускається без tkinter або дисплея)."""
import pytest

pytestmark = pytest.mark.gui
tk = pytest.importorskip("tkinter")


@pytest.fixture
def app(tmp_path):
    from tests.conftest import make_xlsx
    try:
        from app import App
        a = App(str(make_xlsx(tmp_path / "mini.xlsx")))
    except tk.TclError:
        pytest.skip("немає дисплея")
    a.withdraw()
    yield a
    a.destroy()


def test_lists_and_summary(app):
    d = app.directory
    app.main_cb.set(d.find("A32.1").name)
    app.slot_cbs[0].set(d.find("G11").name)
    app.refresh()
    assert all("СП" in d.find(n).cats for n in app.slot_cbs[1]["values"])
    assert app.summary.cget("text").startswith("✖")
    app.slot_cbs[1].set(d.find("R26.2").name)
    app.refresh()
    assert app.summary.cget("text").startswith("✔")


def test_search_filter(app):
    app.main_cb.set("геміпл")

    class E:
        keysym = "a"
    app.main_cb._filter(E())
    assert all("геміпл" in v.lower() for v in app.main_cb["values"])


def test_clear_all(app):
    app.main_cb.set(app.directory.find("A32.1").name)
    app.clear_all()
    assert app.main_cb.get() == "" and "Оберіть" in app.summary.cget("text")
