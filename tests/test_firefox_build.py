"""Збирання версії для Firefox: той самий код, manifest з browser_specific_settings.gecko, .xpi з файлами в корені."""
import json
import zipfile

import build_firefox


def test_build(tmp_path, monkeypatch):
    monkeypatch.setattr(build_firefox, "DIST", tmp_path)
    monkeypatch.setattr(build_firefox, "OUT", tmp_path / "firefox")
    monkeypatch.setattr(build_firefox, "XPI", tmp_path / "a.xpi")
    xpi = build_firefox.build()
    with zipfile.ZipFile(xpi) as z:
        names = set(z.namelist())
        m = json.loads(z.read("manifest.json"))
    assert {"manifest.json", "background.js", "panel.js", "logic.js", "fill.js", "directory.js"} <= names
    assert "icons/icon16.png" in names
    g = m["browser_specific_settings"]["gecko"]
    assert g["id"].endswith("@askep.local") and g["data_collection_permissions"] == {"required": ["none"]}
    assert m["manifest_version"] == 3 and set(m["permissions"]) == {"activeTab", "scripting", "storage"}
    assert m["background"] == {"scripts": ["background.js"]}


def test_cross_browser_api_and_no_innerhtml():
    for f in ("background.js", "panel.js"):
        src = (build_firefox.SRC / f).read_text(encoding="utf-8")
        assert 'typeof browser !== "undefined" ? browser' in src
        assert "innerHTML" not in src             # вимога перевірки addons.mozilla.org


def test_chrome_manifest_service_worker():
    m = json.loads((build_firefox.SRC / "manifest.json").read_text(encoding="utf-8"))
    assert m["background"] == {"service_worker": "background.js"}
    assert "default_popup" not in m["action"]
