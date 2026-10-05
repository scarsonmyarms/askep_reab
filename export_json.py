"""
Експорт довідника у JSON для розширення Chrome.

Розбір формул (стовпець O), категорій і парних кодів †/* виконується тут, у Python
(ця логіка покрита тестами), а розширення отримує вже готові дані.

Запуск:
    python export_json.py tests/dod1.xlsx extension/directory.json
Після оновлення довідника запустіть скрипт ще раз і перезавантажте розширення
(chrome://extensions → «Оновити»).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from coding_rules import EXCLUSIONS, Directory


def export(xlsx: str, out: str) -> int:
    d = Directory(xlsx)
    data = {
        "source": Path(xlsx).name,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "items": [
            {
                "name": x.name,
                "code": x.code,
                "mark": x.mark,
                "cats": sorted(x.cats),
                "main_text": x.main_text,
                "formula": x.formula,
                "groups": [{"kind": g.kind, "tokens": g.tokens, "text": g.text} for g in x.groups],
                "pair_tokens": x.pair_tokens,
                "pair_text": x.pair_text,
                "pair_flag": x.pair_flag,
            }
            for x in d.items
        ],
        "exclusions": [list(e) for e in EXCLUSIONS],
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(data["items"])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Використання: python export_json.py <довідник.xlsx> <directory.json>")
    n = export(sys.argv[1], sys.argv[2])
    print(f"Експортовано {n} діагнозів у {sys.argv[2]}")
