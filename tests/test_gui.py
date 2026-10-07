"""Димовий тест графічного інтерфейсу (пропускається без tkinter або дисплея)."""
import pytest

pytestmark = pytest.mark.gui
tk = pytest.importorskip("tkinter")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    """Одне вікно на весь модуль: повторне створення Tk у Python 3.14 під Windows буває нестабільним."""
    from conftest import make_xlsx
    try:
        from app import App
        a = App(str(make_xlsx(tmp_path_factory.mktemp("gui") / "mini.xlsx")))
    except tk.TclError as e:
        pytest.skip(f"tkinter недоступний: {e}")
    a.withdraw()
    yield a
    a.destroy()


@pytest.fixture(autouse=True)
def _reset(app):
    app.clear_all()
    yield


def test_role_slots(app):
    """Поля за ролями: A32.1 (формула «ФО» + Z) → поле ФО, поле Z (Z50.x), необов'язкове."""
    d = app.directory
    app.main_cb.set(d.find("A32.1").name)
    app.refresh()
    assert [s.role for s in app.plan] == ["main", "main", "free"]
    assert all("ФО" in d.find(n).cats for n in app.slot_cbs[0]["values"])
    assert all("Z" in d.find(n).cats for n in app.slot_cbs[1]["values"])
    assert app.summary.cget("text").startswith("✖")
    app.slot_cbs[0].set(d.find("G11").name)
    app.slot_cbs[1].set(d.find("Z50.0").name)
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


def test_ambulatory_switch(app):
    d = app.directory
    app.main_cb.set(d.find("A32.1").name)
    app.setting.set("Амбулаторія")
    app.refresh()
    text = app.out.get("1.0", "end")
    assert "ПОСЛУГИ АМБУЛАТОРНОЇ РЕАБІЛІТАЦІЇ" in text and "АР2" in text
    app.sr_record.set(True)
    app.refresh()
    assert "АР1" in app.out.get("1.0", "end")
    app.setting.set("Стаціонар")
    app.refresh()
    assert "ПОСЛУГИ АМБУЛАТОРНОЇ" not in app.out.get("1.0", "end")
