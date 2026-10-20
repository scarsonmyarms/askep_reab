"""
Збирання версії розширення для Firefox.

Код розширення спільний (extension/); для Firefox відрізняється лише manifest.json:
додається browser_specific_settings.gecko (ідентифікатор розширення й мінімальна версія Firefox).

Запуск:
    python build_firefox.py
Результат:
    dist/firefox/                       — розпакована версія (about:debugging → «Тимчасово завантажити додаток»)
    dist/askep_rehab_firefox.xpi         — архів для підпису на addons.mozilla.org або встановлення
"""
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "extension"
DIST = ROOT / "dist"
OUT = DIST / "firefox"
XPI = DIST / "askep_rehab_firefox.xpi"

GECKO = {
    "id": "askep-rehab-coding@askep.local",   # постійний ідентифікатор (потрібен для підпису й оновлень)
    "strict_min_version": "128.0",           # Firefox 128 ESR і новіші (Manifest V3, scripting, CSS :has)
    # розширення не збирає й не передає даних (усе лишається в браузері)
    "data_collection_permissions": {"required": ["none"]},
}


def build() -> Path:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT)
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    manifest["browser_specific_settings"] = {"gecko": GECKO}
    # Firefox (MV3) запускає фоновий код як background.scripts, а не service_worker
    if "service_worker" in manifest.get("background", {}):
        manifest["background"] = {"scripts": [manifest["background"]["service_worker"]]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    DIST.mkdir(exist_ok=True)
    if XPI.exists():
        XPI.unlink()
    with zipfile.ZipFile(XPI, "w", zipfile.ZIP_DEFLATED) as z:   # файли в корені архіву (вимога Firefox)
        for f in sorted(OUT.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(OUT).as_posix())
    return XPI


if __name__ == "__main__":
    print(f"Готово: {build()}")
