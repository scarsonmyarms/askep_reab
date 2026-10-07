"""
Узгодженість логіки розширення Chrome (extension/logic.js) з Python (coding_rules.py).
Ті самі випадкові сценарії перевіряються обома реалізаціями; звіти мають збігатися дослівно.
Потрібен Node.js (пропускається, якщо node не встановлено).
"""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from coding_rules import PERIOD_LONG, PERIOD_POST, SETTING_INPATIENT, SETTING_OUTPATIENT, plan_slots, slot_candidates, slot_fits, validate
from export_json import export

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js не встановлено")
RUNNER = Path(__file__).with_name("js_parity_runner.js")


def scenarios(directory, n, seed=2026):
    rnd = random.Random(seed)
    items = directory.items
    out = []
    for _ in range(n):
        period = rnd.choice([PERIOD_POST, PERIOD_LONG])
        mains = directory.main_candidates(period)
        main = rnd.choice(mains)
        comps = []
        for i in range(rnd.randint(0, 4)):
            r = rnd.random()
            if r < 0.6:   # як користувач: зі списку поля
                sel = [directory.find(c) for c in comps]
                cand = directory.companion_candidates(main, i, sel)
                comps.append(rnd.choice(cand).name if cand else rnd.choice(items).name)
            elif r < 0.85:
                comps.append(rnd.choice(items).name)
            elif r < 0.95:
                comps.append(rnd.choice(items).code)
            else:
                comps.append("I10 Гіпертензія (поза довідником)")
        out.append({"period": period, "main": main.name, "comps": comps, "st": rnd.random() < 0.3,
                    "setting": rnd.choice([SETTING_INPATIENT, SETTING_OUTPATIENT]), "sr": rnd.random() < 0.5})
    return out


def plan_scenarios(directory, n, seed=7):
    """Імітація користувача: поле за полем обирає варіант зі списку поля (іноді лишає порожнім)."""
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        period = rnd.choice([PERIOD_POST, PERIOD_LONG])
        main = rnd.choice(directory.main_candidates(period))
        values = {}
        for _step in range(6):
            slots = plan_slots(directory, main, values)
            empty = [i for i, x in enumerate(slots) if not x.value]
            if not empty or rnd.random() < 0.15:
                break
            i = empty[0]
            cand = slot_candidates(directory, main, slots, i)
            if cand and rnd.random() < 0.9:
                values[slots[i].key] = rnd.choice(cand).name
            else:
                values[slots[i].key] = "I10 Гіпертензія (поза довідником)"
        out.append({"period": period, "main": main.name, "values": values, "comps": [], "st": rnd.random() < 0.3,
                    "setting": rnd.choice([SETTING_INPATIENT, SETTING_OUTPATIENT]), "sr": rnd.random() < 0.5})
    return out


def py_plan_result(directory, s):
    main = directory.find(s["main"])
    slots = plan_slots(directory, main, s["values"])
    rep = validate(directory, s["period"], s["main"], [x.value for x in slots], s["st"],
                   setting=s["setting"], sr_record=s["sr"])
    L = lambda ls: [{"level": l.level, "text": l.text} for l in ls]
    return {
        "plan": [[x.key, x.role, x.label, x.value, len(slot_candidates(directory, main, slots, i)), slot_fits(x)]
                 for i, x in enumerate(slots)],
        "report": {"main": L(rep.main), "main_groups": L(rep.main_groups), "exclusions": L(rep.exclusions),
                   "summary": {"level": rep.summary.level, "text": rep.summary.text}, "services": L(rep.services),
                   "companions": [[n, L(ls)] for n, ls in rep.companions]},
    }


def py_result(directory, s):
    if "values" in s:
        return py_plan_result(directory, s)
    rep = validate(directory, s["period"], s["main"], s["comps"], s["st"], setting=s["setting"], sr_record=s["sr"])
    L = lambda ls: [{"level": l.level, "text": l.text} for l in ls]
    main = directory.find(s["main"])
    sel = [directory.find(c) for c in s["comps"]]
    return {
        "report": {"main": L(rep.main), "main_groups": L(rep.main_groups), "exclusions": L(rep.exclusions),
                   "summary": {"level": rep.summary.level, "text": rep.summary.text}, "services": L(rep.services),
                   "companions": [[n, L(ls)] for n, ls in rep.companions]},
        "lists": [len(directory.companion_candidates(main, i, sel)) for i in range(len(sel))],
        "mains": len(directory.main_candidates(s["period"])),
    }


def run_parity(directory, xlsx_path, tmp_path, n, nszu_files=None):
    dj = tmp_path / "directory.json"
    export(xlsx_path, str(dj), nszu_files=nszu_files)
    sc = scenarios(directory, n) + plan_scenarios(directory, n // 2)
    sj = tmp_path / "scenarios.json"
    sj.write_text(json.dumps(sc, ensure_ascii=False), encoding="utf-8")
    res = subprocess.run([NODE, str(RUNNER), str(dj), str(sj)], capture_output=True, check=True)
    js = json.loads(res.stdout.decode("utf-8"))
    for s, j in zip(sc, js):
        assert j == py_result(directory, s), f"Розбіжність Python/JS: {s}"


def test_parity_mini(mini_dir, tmp_path):
    from conftest import make_xlsx
    xlsx = make_xlsx(tmp_path / "mini.xlsx")
    run_parity(mini_dir, str(xlsx), tmp_path, 200)


@pytest.mark.real
def test_parity_real(real_dir, request, tmp_path):
    path = getattr(real_dir, "path", None)
    if path is None:
        pytest.skip("шлях до довідника невідомий")
    run_parity(real_dir, path, tmp_path, 400)


@pytest.mark.real
def test_parity_real_nszu(real_nszu, tmp_path):
    """Те саме з файлами НСЗУ: формули, пари †/* і перелік основних з нових файлів."""
    run_parity(real_nszu, real_nszu.path, tmp_path, 400, nszu_files="auto")
