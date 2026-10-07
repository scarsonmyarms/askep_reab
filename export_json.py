"""
Експорт довідника у JSON для розширення Chrome.

Розбір формул (стовпець O), категорій і парних кодів †/* виконується тут, у Python
(ця логіка покрита тестами), а розширення отримує вже готові дані.

Запуск:
    python export_json.py tests/dod1.xlsx extension/directory.json
Файли НСЗУ (перелік основних, формули, пари †/*) підхоплюються автоматично з тієї самої папки,
що й довідник.
Після оновлення довідника запустіть скрипт ще раз і перезавантажте розширення
(chrome://extensions → «Оновити»).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from coding_rules import CASE_GROUPS, EXCLUSIONS, Directory


def export(xlsx: str, out: str, nszu_files="auto") -> int:
    d = Directory(xlsx, nszu_files=nszu_files)
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
                "main_conds": x.main_conds,
                "formula": x.formula,
                "comp_formula": x.comp_formula,
                "groups": [{"kind": g.kind, "tokens": g.tokens, "text": g.text} for g in x.groups],
                "comp_groups": (None if x.comp_groups is None or x.comp_groups is x.groups
                                else [{"kind": g.kind, "tokens": g.tokens, "text": g.text} for g in x.comp_groups]),
                "pair_tokens": x.pair_tokens,
                "pair_text": x.pair_text,
                "pair_flag": x.pair_flag,
                "source": x.source,
                "row": x.row,
            }
            for x in d.items
        ],
        "sources": d.sources,
        "ambulatory": d.ambulatory,
        "exclusions": [list(e) for e in EXCLUSIONS],
        "case_groups": [{"kind": g.kind, "tokens": g.tokens, "text": g.text} for g in CASE_GROUPS],
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(data["items"])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Використання: python export_json.py <довідник.xlsx> <directory.json>")
    n = export(sys.argv[1], sys.argv[2])
    print(f"Експортовано {n} діагнозів у {sys.argv[2]}")
